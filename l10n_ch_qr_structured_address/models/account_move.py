# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _l10n_ch_qr_bill_applicable(self):
        """True when this move would produce a Swiss QR-bill: a customer
        invoice / credit note with a bank account eligible for ``ch_qr``
        (IBAN, debtor in CH/LI, currency CHF or EUR).

        Deliberately independent of ``display_qr_code`` / the company setting
        "QR codes on invoices": that setting only governs the QR image inside
        the invoice PDF, whereas the QR-bill is produced by the separate
        report ``l10n_ch.l10n_ch_qr_report`` and the e-mail attachment.
        """
        self.ensure_one()
        return (
            self.is_sale_document(include_receipts=False)
            and self.partner_bank_id
            and self.partner_bank_id._eligible_for_qr_code('ch_qr', self.partner_id, self.currency_id)
        )

    def _l10n_ch_qr_check_addresses(self):
        """Raise a UserError if the Swiss QR-bill of this move cannot be
        generated with structured addresses.  No-op when no QR-bill applies."""
        for move in self:
            if not move._l10n_ch_qr_bill_applicable():
                continue
            try:
                move.partner_bank_id._build_qr_code_vals(
                    move.amount_residual,
                    move.ref or move.name,
                    move.payment_reference,
                    move.currency_id,
                    move.partner_id,
                    'ch_qr',
                    silent_errors=False,
                )
            except UserError as error:
                raise UserError(_("%(move)s: %(error)s", move=move.display_name, error=error.args[0])) from error

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        """Validate creditor and debtor addresses when posting.

        Runs *after* super() because the QR reference (payment_reference) is
        only assigned during posting; the UserError rolls the whole posting
        back, so the invoice stays in draft.
        """
        posted = super()._post(soft=soft)
        posted.filtered(lambda m: m.company_id.l10n_ch_qr_check_on_post)._l10n_ch_qr_check_addresses()
        return posted

    def print_ch_qr_bill(self):
        """'Print QR-bill' button: give the precise address error instead of
        the generic l10n_ch message."""
        self.ensure_one()
        self._l10n_ch_qr_check_addresses()
        return super().print_ch_qr_bill()
