# -*- coding: utf-8 -*-

import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_resource


class SaleLineSizePricingWizard(models.TransientModel):
    _name = 'sale.line.size.pricing.wizard'
    _description = 'Add Sale Line From Size Pricing'

    sale_order_line_id = fields.Many2one('sale.order.line', string='Source Line', required=True, readonly=True)
    order_id = fields.Many2one(related='sale_order_line_id.order_id', string='Order', readonly=True)
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
        line_id = self.env.context.get('default_sale_order_line_id')
        if line_id:
            line = self.env['sale.order.line'].browse(line_id)
            if 'size_text' in fields_list:
                res['size_text'] = line._get_size_pricing_text()
            if 'square_meter' in fields_list:
                res['square_meter'] = line._get_size_square_meter()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            line_id = vals.get('sale_order_line_id')
            if line_id:
                line = self.env['sale.order.line'].browse(line_id)
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

    def _get_pricelist_price(self):
        self.ensure_one()
        order = self.order_id
        if not order.pricelist_id:
            raise UserError(_('Please set a pricelist on the sale order first.'))
        if self.square_meter <= 0:
            raise UserError(_('Square meter must be greater than zero.'))

        price_rule = order.pricelist_id._compute_price_rule(
            [(self.product_id, self.square_meter, order.partner_id)],
            date=fields.Date.to_date(order.date_order) if order.date_order else fields.Date.context_today(self),
            uom_id=self.product_id.uom_id.id,
        )
        price, rule_id = price_rule.get(self.product_id.id, (0.0, False))
        if not rule_id:
            raise UserError(
                _('No pricelist rule was found for %(product)s at %(sqm)s m2 in %(pricelist)s.') % {
                    'product': self.product_id.display_name,
                    'sqm': self.square_meter,
                    'pricelist': order.pricelist_id.display_name,
                }
            )
        return price

    def _prepare_new_line_vals(self, price):
        self.ensure_one()
        order = self.order_id
        product = self.product_id.with_context(
            lang=order.partner_id.lang,
            partner=order.partner_id.id,
        )
        taxes = product.taxes_id.filtered(lambda tax: tax.company_id == order.company_id)
        if order.fiscal_position_id:
            taxes = order.fiscal_position_id.map_tax(taxes)

        name = product.get_product_multiline_description_sale() or product.display_name
        if self.description and self.description.strip():
            name = '%s\n%s' % (name, self.description.strip())

        values = {
            'order_id': order.id,
            'product_id': product.id,
            'name': name,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 1.0,
            'price_unit': price,
            'sequence2': self.sale_order_line_id.sequence2 + 1,
            'tax_id': [(6, 0, taxes.ids)],
        }
        if 'section_id' in self.sale_order_line_id._fields and self.sale_order_line_id.section_id:
            values['section_id'] = self.sale_order_line_id.section_id.id
        return values

    def action_add_line(self):
        self.ensure_one()
        if not self.sale_order_line_id or not self.order_id:
            raise UserError(_('Please open this wizard from a sale order line.'))
        if not self.product_id:
            raise UserError(_('Please select a product.'))
        if self.square_meter <= 0:
            raise UserError(_('Square meter must be greater than zero.'))
        if self.price_unit <= 0:
            raise UserError(_('Unit price must be greater than zero.'))

        following_lines = self.env['sale.order.line'].search(
            [
                ('order_id', '=', self.order_id.id),
                ('sequence2', '>', self.sale_order_line_id.sequence2),
            ],
            order='sequence2 desc',
        )
        for line in following_lines:
            line.sequence2 += 1

        self.env['sale.order.line'].create(self._prepare_new_line_vals(self.price_unit))
        if hasattr(self.order_id, '_reset_sequence'):
            self.order_id._reset_sequence()
        return {'type': 'ir.actions.act_window_close'}
