# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleLineSizePricingWizard(models.TransientModel):
    _name = 'sale.line.size.pricing.wizard'
    _description = 'Add Sale Line From Size Pricing'

    sale_order_line_id = fields.Many2one('sale.order.line', string='Source Line', required=True, readonly=True)
    order_id = fields.Many2one(related='sale_order_line_id.order_id', string='Order', readonly=True)
    size_text = fields.Char(string='Size', compute='_compute_size_details', readonly=True)
    square_meter = fields.Float(string='Square Meter', digits=(16, 4), compute='_compute_size_details', readonly=True)
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain="[('product_tmpl_id.show_in_size_pricing_popup', '=', True)]",
    )

    @api.depends('sale_order_line_id')
    def _compute_size_details(self):
        for wizard in self:
            line = wizard.sale_order_line_id
            wizard.size_text = line._get_size_pricing_text() if line else False
            wizard.square_meter = line._get_size_square_meter() if line else 0.0

    def _get_pricelist_price(self):
        self.ensure_one()
        order = self.order_id
        if not order.pricelist_id:
            raise UserError(_('Please set a pricelist on the sale order first.'))
        if self.square_meter <= 0:
            raise UserError(_('Could not calculate square meters from the line size.'))

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

        values = {
            'order_id': order.id,
            'product_id': product.id,
            'name': product.get_product_multiline_description_sale() or product.display_name,
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

        following_lines = self.env['sale.order.line'].search(
            [
                ('order_id', '=', self.order_id.id),
                ('sequence2', '>', self.sale_order_line_id.sequence2),
            ],
            order='sequence2 desc',
        )
        for line in following_lines:
            line.sequence2 += 1

        price = self._get_pricelist_price()
        self.env['sale.order.line'].create(self._prepare_new_line_vals(price))
        if hasattr(self.order_id, '_reset_sequence'):
            self.order_id._reset_sequence()
        return {'type': 'ir.actions.act_window_close'}
