# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError

from ..utils import grosse_format_warning_message, is_valid_grosse_format, parse_square_meter


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_size_pricing_text(self):
        self.ensure_one()
        if 'x_studio_groesse' in self._fields and self.x_studio_groesse:
            return self.x_studio_groesse
        if self.product_id and self.product_id.grosse:
            return self.product_id.grosse
        return ''

    def _get_size_square_meter(self):
        self.ensure_one()
        return parse_square_meter(self._get_size_pricing_text())

    def action_open_invoice_size_pricing_wizard(self):
        self.ensure_one()
        if self.display_type:
            raise UserError(_('This action can only be used on product lines.'))
        if not self.product_id:
            raise UserError(_('Please select a product on the source line first.'))
        if self.move_id.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_('This action is only available on customer invoices/credit notes.'))
        if self.move_id.state != 'draft':
            raise UserError(_('You can only add size priced lines on draft invoices.'))

        size_text = self._get_size_pricing_text()
        if size_text and not is_valid_grosse_format(size_text):
            raise UserError(_(grosse_format_warning_message()))
        if self._get_size_square_meter() <= 0:
            raise UserError(_('Could not calculate square meters from the line size.'))

        return {
            'name': _('Add Size Priced Invoice Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'invoice.line.size.pricing.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_move_line_id': self.id,
            },
        }
