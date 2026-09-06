# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
"""Integration tests: payload, validation hooks, posting.

Run on Odoo.sh (test branch) or locally with::

    odoo-bin -d <db> -i l10n_ch_qr_structured_address --test-tags /l10n_ch_qr_structured_address --stop-after-init
"""
import time

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

CH_IBAN = 'CH15 3881 5158 3845 3843 7'   # plain IBAN  → SCOR / NON
QR_IBAN = 'CH21 3080 8001 2345 6782 7'   # QR-IBAN     → QRR

# 0-based indexes of the 31-line Odoo 15 payload
CRED_TYPE, CRED_NAME, CRED_STREET, CRED_NUMBER, CRED_ZIP, CRED_CITY, CRED_COUNTRY = range(4, 11)
DEBT_TYPE, DEBT_NAME, DEBT_STREET, DEBT_NUMBER, DEBT_ZIP, DEBT_CITY, DEBT_COUNTRY = range(20, 27)
REF_TYPE, REF, MESSAGE, TRAILER = 27, 28, 29, 30


@tagged('post_install_l10n', 'post_install', '-at_install', 'l10n_ch_qr')
class TestSwissQRStructuredAddress(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_ch.l10nch_chart_template'):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.ch = cls.env.ref('base.ch')
        cls.chf = cls.env.ref('base.CHF')
        cls.company = cls.env.company
        cls.company.write({
            'l10n_ch_qr_require_building_number': True,
            'l10n_ch_qr_check_on_post': True,
        })
        cls.company.partner_id.write({
            'name': 'Baur Insektenschutz AG',
            'street': 'Eichenweg 11',
            'street2': False,
            'zip': '3628',
            'city': 'Uttigen',
            'country_id': cls.ch.id,
        })
        cls.bank_iban = cls.env['res.partner.bank'].create({
            'acc_number': CH_IBAN,
            'partner_id': cls.company.partner_id.id,
        })
        cls.bank_qr_iban = cls.env['res.partner.bank'].create({
            'acc_number': QR_IBAN,
            'partner_id': cls.company.partner_id.id,
        })
        cls.company_data['default_journal_sale'].invoice_reference_model = 'ch'
        cls.customer = cls.env['res.partner'].create({
            'name': 'Muster AG',
            'street': 'Rue de la Gare 12a',
            'street2': False,
            'zip': '1003',
            'city': 'Lausanne',
            'country_id': cls.ch.id,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _payload(self, bank=None, partner=None, amount=150.0, structured_ref='', free=''):
        bank = bank or self.bank_iban
        return bank._get_qr_vals('ch_qr', amount, self.chf, partner or self.customer, free, structured_ref)

    def _create_invoice(self, partner=None, bank=None, currency=None):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': (partner or self.customer).id,
            'partner_bank_id': (bank or self.bank_qr_iban).id,
            'currency_id': (currency or self.chf).id,
            'invoice_date': time.strftime('%Y-%m-%d'),
            'journal_id': self.company_data['default_journal_sale'].id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Insektenschutz',
                'product_id': self.product_a.id,
                'quantity': 1,
                'price_unit': 150.0,
            })],
        })

    # ------------------------------------------------------------------
    # payload
    # ------------------------------------------------------------------
    def test_payload_uses_type_S_for_both_blocks(self):
        lines = self._payload()
        self.assertEqual(len(lines), 31)
        self.assertEqual(lines[0:3], ['SPC', '0200', '1'])
        self.assertEqual(lines[CRED_TYPE], 'S')
        self.assertEqual(lines[CRED_NAME], 'Baur Insektenschutz AG')
        self.assertEqual(lines[CRED_STREET:CRED_COUNTRY + 1], ['Eichenweg', '11', '3628', 'Uttigen', 'CH'])
        self.assertEqual(lines[DEBT_TYPE], 'S')
        self.assertEqual(lines[DEBT_NAME], 'Muster AG')
        self.assertEqual(lines[DEBT_STREET:DEBT_COUNTRY + 1], ['Rue de la Gare', '12a', '1003', 'Lausanne', 'CH'])
        self.assertEqual(lines[11:18], [''] * 7, 'Ultimate creditor block must stay empty')
        self.assertEqual(lines[TRAILER], 'EPD')
        self.assertNotIn('K', (lines[CRED_TYPE], lines[DEBT_TYPE]))
        self.assertLessEqual(len('\n'.join(lines)), 997)

    def test_reference_types_unchanged(self):
        lines = self._payload(bank=self.bank_iban)
        self.assertEqual(lines[REF_TYPE], 'NON')
        lines = self._payload(bank=self.bank_iban, structured_ref='RF18 5390 0754 7034')
        self.assertEqual(lines[REF_TYPE], 'SCOR')
        self.assertEqual(lines[REF], 'RF18539007547034')
        lines = self._payload(bank=self.bank_qr_iban, structured_ref='210000000003139471430009017')
        self.assertEqual(lines[REF_TYPE], 'QRR')
        self.assertEqual(lines[3], 'CH2130808001234567827')

    def test_baur_letter_suffix_pattern(self):
        self.customer.street = 'Oberdorfstrasse 20 A'
        lines = self._payload()
        self.assertEqual(lines[DEBT_STREET:DEBT_NUMBER + 1], ['Oberdorfstrasse', '20 A'])

    def test_care_of_pattern(self):
        self.customer.write({'street': 'c/o Ruchti Partner AG', 'street2': 'Auweg 41'})
        lines = self._payload()
        self.assertEqual(lines[DEBT_STREET:DEBT_NUMBER + 1], ['Auweg', '41'])

    def test_street2_is_not_appended_to_number(self):
        self.customer.write({'street': 'Rue de la Gare 12a', 'street2': 'c/o Meier'})
        lines = self._payload()
        self.assertEqual(lines[DEBT_NUMBER], '12a')

    def test_debtor_name_is_commercial_partner(self):
        contact = self.env['res.partner'].create({
            'name': 'Hans Muster',
            'parent_id': self.customer.id,
            'type': 'invoice',
            'street': 'Seestrasse 7',
            'zip': '8002',
            'city': 'Zürich',
            'country_id': self.ch.id,
        })
        lines = self._payload(partner=contact)
        self.assertEqual(lines[DEBT_NAME], 'Muster AG')
        self.assertEqual(lines[DEBT_STREET:DEBT_CITY + 1], ['Seestrasse', '7', '8002', 'Zürich'])

    def test_sanitising(self):
        self.customer.write({'name': 'Muster\nAG “Zürich”', 'city': 'Zürich ☺'})
        lines = self._payload(free='Rechnung\r\nNr. 1 – Danke')
        self.assertEqual(lines[DEBT_NAME], 'Muster AG "Zürich"')
        self.assertEqual(lines[DEBT_CITY], 'Zürich')
        self.assertEqual(lines[MESSAGE], 'Rechnung Nr. 1 - Danke')
        self.assertTrue(all('\n' not in line for line in lines))

    def test_postal_code_prefix_stripped(self):
        self.customer.zip = 'CH-1003'
        self.assertEqual(self._payload()[DEBT_ZIP], '1003')

    def test_missing_number_allowed_when_setting_off(self):
        self.company.l10n_ch_qr_require_building_number = False
        self.customer.street = 'Industriestrasse'
        self.assertEqual(self._payload()[DEBT_STREET:DEBT_NUMBER + 1], ['Industriestrasse', ''])

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    def test_check_errors_lists_every_problem(self):
        self.customer.write({'street': 'Industriestrasse', 'zip': False, 'city': False})
        message = self.bank_iban._check_for_qr_code_errors('ch_qr', 150.0, self.chf, self.customer, '', '')
        self.assertTrue(message)
        self.assertIn('postal code', message)
        self.assertIn('city', message)
        self.assertIn("'Industriestrasse' has no building number", message)
        self.assertIn('Muster AG', message)

    def test_check_errors_creditor(self):
        self.company.partner_id.street = 'Eichenweg'
        message = self.bank_iban._check_for_qr_code_errors('ch_qr', 150.0, self.chf, self.customer, '', '')
        self.assertIn('creditor', message)
        self.assertIn("'Eichenweg' has no building number", message)

    def test_check_errors_none_when_complete(self):
        self.assertFalse(self.bank_iban._check_for_qr_code_errors('ch_qr', 150.0, self.chf, self.customer, '', ''))

    def test_qr_iban_still_requires_qr_reference(self):
        # the l10n_ch check (super) must still be reached when the address is fine
        message = self.bank_qr_iban._check_for_qr_code_errors('ch_qr', 150.0, self.chf, self.customer, '', 'not-a-qrr')
        self.assertTrue(message)
        self.assertIn('QR-reference', message)

    # ------------------------------------------------------------------
    # posting / printing
    # ------------------------------------------------------------------
    def test_posting_complete_address_succeeds_with_qrr(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(invoice.payment_reference)
        lines = invoice.partner_bank_id._get_qr_vals(
            'ch_qr', invoice.amount_residual, invoice.currency_id, invoice.partner_id,
            invoice.ref or invoice.name, invoice.payment_reference)
        self.assertEqual(lines[REF_TYPE], 'QRR')
        self.assertEqual(lines[DEBT_TYPE], 'S')

    def test_posting_blocked_when_debtor_has_no_building_number(self):
        self.customer.street = 'Industriestrasse'
        invoice = self._create_invoice()
        with self.assertRaises(UserError) as cm:
            invoice.action_post()
        self.assertIn('Industriestrasse', str(cm.exception))
        self.assertEqual(invoice.state, 'draft')

    def test_posting_blocked_when_debtor_has_no_zip(self):
        self.customer.zip = False
        invoice = self._create_invoice()
        with self.assertRaises(UserError):
            invoice.action_post()
        self.assertEqual(invoice.state, 'draft')

    def test_posting_blocked_when_creditor_incomplete(self):
        self.company.partner_id.street = 'Eichenweg'
        invoice = self._create_invoice()
        with self.assertRaises(UserError) as cm:
            invoice.action_post()
        self.assertIn('creditor', str(cm.exception))

    def test_posting_not_blocked_when_check_on_post_disabled(self):
        self.company.l10n_ch_qr_check_on_post = False
        self.customer.street = 'Industriestrasse'
        invoice = self._create_invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        # printing the QR-bill still validates
        with self.assertRaises(UserError):
            invoice.print_ch_qr_bill()

    def test_posting_not_blocked_for_foreign_debtor(self):
        self.customer.write({'country_id': self.env.ref('base.de').id, 'street': 'Hauptstrasse'})
        invoice = self._create_invoice()
        invoice.action_post()  # not eligible for ch_qr → no QR-bill → no check
        self.assertEqual(invoice.state, 'posted')

    def test_posting_not_blocked_without_bank_account(self):
        self.customer.street = 'Industriestrasse'
        invoice = self._create_invoice()
        invoice.partner_bank_id = False
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

    def test_vendor_bill_never_checked(self):
        self.customer.street = 'Industriestrasse'
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.customer.id,
            'invoice_date': time.strftime('%Y-%m-%d'),
            'invoice_line_ids': [(0, 0, {'name': 'x', 'product_id': self.product_a.id, 'quantity': 1, 'price_unit': 10.0})],
        })
        bill.action_post()
        self.assertEqual(bill.state, 'posted')

    def test_print_button_gives_precise_error(self):
        invoice = self._create_invoice()
        invoice.action_post()
        self.customer.street = 'Industriestrasse'
        with self.assertRaises(UserError) as cm:
            invoice.print_ch_qr_bill()
        self.assertIn("'Industriestrasse' has no building number", str(cm.exception))

    def test_qr_bill_report_renders(self):
        invoice = self._create_invoice()
        invoice.action_post()
        pdf, _type = self.env.ref('l10n_ch.l10n_ch_qr_report')._render_qweb_pdf(invoice.ids)
        self.assertTrue(pdf)
