# -*- coding: utf-8 -*-
import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource


class InvoiceLineSizePricingWizard(models.TransientModel):
    _name = 'invoice.line.size.pricing.wizard'
    _description = 'Add Invoice Line From Size Pricing'

    account_move_line_id = fields.Many2one('account.move.line', string='Source Line', required=True, readonly=True)
    move_id = fields.Many2one(related='account_move_line_id.move_id', string='Invoice', readonly=True)
    size_text = fields.Char(string='Size', readonly=True)
    square_meter = fields.Float(string='Square Meter', digits=(16, 4))
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain="[('product_tmpl_id.show_in_size_pricing_popup', '=', True)]",
    )
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    description = fields.Text(string='Description')
    size_reference_image = fields.Image(string='Reference Matrix', default=lambda self: self._default_size_reference_image())

    @api.model
    def _default_size_reference_image(self):
        image_path = get_module_resource(
            'baur_sale_size_pricing', 'static/src/img', 'size_matrix_reference.png'
        )
        if not image_path:
            return False
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read())

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get('default_account_move_line_id')
        if line_id:
            line = self.env['account.move.line'].browse(line_id)
            if 'size_text' in fields_list:
                res['size_text'] = line._get_size_pricing_text()
            if 'square_meter' in fields_list:
                res['square_meter'] = line._get_size_square_meter()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            line_id = vals.get('account_move_line_id')
            if line_id:
                line = self.env['account.move.line'].browse(line_id)
                vals.setdefault('size_text', line._get_size_pricing_text())
                vals.setdefault('square_meter', line._get_size_square_meter())
        records = super().create(vals_list)
        for wizard in records.filtered(lambda w: w.product_id and not w.price_unit):
            try:
                wizard.price_unit = wizard._get_pricelist_price()
            except UserError:
                wizard.price_unit = 0.0
        return records

    @api.onchange('product_id', 'square_meter')
    def _onchange_price_from_pricelist(self):
        for wizard in self:
            if not wizard.product_id or wizard.square_meter <= 0:
                continue
            try:
                wizard.price_unit = wizard._get_pricelist_price()
            except UserError:
                wizard.price_unit = 0.0

    def _get_pricelist(self):
        self.ensure_one()
        sale_lines = self.account_move_line_id.sale_line_ids
        sale_orders = sale_lines.mapped('order_id')
        return sale_orders[:1].pricelist_id

    def _get_pricelist_price(self):
        self.ensure_one()
        pricelist = self._get_pricelist()
        if not pricelist:
            raise UserError(_('No sale-order pricelist was found on the source invoice line.'))
        if self.square_meter <= 0:
            raise UserError(_('Square meter must be greater than zero.'))

        partner = self.move_id.partner_id
        price_rule = pricelist._compute_price_rule(
            [(self.product_id, self.square_meter, partner)],
            date=fields.Date.to_date(self.move_id.invoice_date) if self.move_id.invoice_date else fields.Date.context_today(self),
            uom_id=self.product_id.uom_id.id,
        )
        price, rule_id = price_rule.get(self.product_id.id, (0.0, False))
        if not rule_id:
            raise UserError(
                _('No pricelist rule was found for %(product)s at %(sqm)s m2 in %(pricelist)s.') % {
                    'product': self.product_id.display_name,
                    'sqm': self.square_meter,
                    'pricelist': pricelist.display_name,
                }
            )
        return price

    def _prepare_new_line_vals(self):
        self.ensure_one()
        move = self.move_id
        product = self.product_id.with_context(
            lang=move.partner_id.lang,
            partner=move.partner_id.id,
        )
        taxes = product.taxes_id.filtered(lambda tax: tax.company_id == move.company_id)
        if move.fiscal_position_id:
            taxes = move.fiscal_position_id.map_tax(taxes)

        name = product.get_product_multiline_description_sale() or product.display_name
        if self.description and self.description.strip():
            name = '%s\n%s' % (name, self.description.strip())

        account = self.account_move_line_id.account_id
        if not account:
            account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_('Missing income account on product/category for invoice line creation.'))

        line_vals = {
            'product_id': product.id,
            'name': name,
            'product_uom_id': product.uom_id.id,
            'sequence': self.account_move_line_id.sequence + 1,
            'quantity': 1.0,
            'price_unit': self.price_unit,
            'account_id': account.id,
            'tax_ids': [(6, 0, taxes.ids)],
        }
        return line_vals

    def action_add_line(self):
        self.ensure_one()
        if not self.account_move_line_id or not self.move_id:
            raise UserError(_('Please open this wizard from an invoice line.'))
        if self.move_id.state != 'draft':
            raise UserError(_('You can only add lines on a draft invoice.'))
        if not self.product_id:
            raise UserError(_('Please select a product.'))
        if self.square_meter <= 0:
            raise UserError(_('Square meter must be greater than zero.'))
        if self.price_unit <= 0:
            raise UserError(_('Unit price must be greater than zero.'))

        following_lines = self.env['account.move.line'].search(
            [
                ('move_id', '=', self.move_id.id),
                ('exclude_from_invoice_tab', '=', False),
                ('sequence', '>', self.account_move_line_id.sequence),
            ],
            order='sequence desc',
        )
        for line in following_lines:
            line.sequence += 1

        move = self.move_id.with_context(check_move_validity=False)
        move.write({'invoice_line_ids': [(0, 0, self._prepare_new_line_vals())]})
        move._recompute_dynamic_lines(recompute_all_taxes=True)
        return {'type': 'ir.actions.act_window_close'}
