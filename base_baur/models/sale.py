# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.

from datetime import timedelta

from odoo import fields, models, api
from dateutil.relativedelta import relativedelta
from odoo.tools import format_date, formatLang, frozendict

from odoo.tools import is_html_empty

class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    def _default_example_amount(self):
        invoice = self.env['account.move'].search([('id', '=', self._context.get('invoice_id'))])
        return invoice.amount_total or 100  # Force default value if the context is set to False

    def _default_example_date(self):
        return self._context.get('example_date') or fields.Date.today()

    display_terms = fields.Boolean(string="Display terms on invoice")
    example_amount = fields.Float(default=_default_example_amount, store=False)
    example_date = fields.Date(string='Date example', default=_default_example_date, store=False)
    example_invalid = fields.Boolean(compute='_compute_example_invalid')
    example_preview = fields.Html(compute='_compute_example_preview')

    @api.depends('line_ids')
    def _compute_example_invalid(self):
        for payment_term in self:
            payment_term.example_invalid = len(payment_term.line_ids.filtered(lambda l: l.value == 'balance')) != 1

    @api.depends('example_amount', 'example_date', 'line_ids.value', 'line_ids.value_amount',
                 'line_ids.days')
    def _compute_example_preview(self):
        for record in self:
            example_preview = ""
            if not record.example_invalid:
                currency = self.env.company.currency_id
                terms = record._compute_terms(
                    date_ref=record.example_date,
                    currency=currency,
                    company=self.env.company,
                    tax_amount=0,
                    tax_amount_currency=0,
                    untaxed_amount=record.example_amount,
                    untaxed_amount_currency=record.example_amount,
                    sign=1)
                for i, info_by_dates in enumerate(record._get_amount_by_date(terms, currency).values()):
                    date = info_by_dates['date']
                    discount_date = info_by_dates['discount_date']
                    amount = info_by_dates['amount']
                    discount_amount = info_by_dates['discounted_amount'] or 0.0
                    example_preview += f"""
                        <div style='margin-left: 20px;'>
                            <b>{i+1}#</b>
                            Installment of
                            <b>{formatLang(self.env, amount, monetary=True, currency_obj=currency)}</b>
                            on 
                            <b style='color: #704A66;'>{date}</b>
                    """
                    if discount_date:
                        example_preview += f"""
                         (<b>{formatLang(self.env, discount_amount, monetary=True, currency_obj=currency)}</b> if paid before <b>{format_date(self.env, terms[i].get('discount_date'))}</b>)
                    """
                    example_preview += "</div>"

            record.example_preview = example_preview
    @api.model
    def _get_amount_by_date(self, terms, currency):
        """
        Returns a dictionary with the amount for each date of the payment term
        (grouped by date, discounted percentage and discount last date,
        sorted by date and ignoring null amounts).
        """
        terms = sorted(terms, key=lambda t: t.get('date'))
        amount_by_date = {}
        for term in terms:
            key = frozendict({
                'date': term['date'],
                'discount_date': term['discount_date'],
                'discount_percentage': term['discount_percentage'],
            })
            results = amount_by_date.setdefault(key, {
                'date': format_date(self.env, term['date']),
                'amount': 0.0,
                'discounted_amount': 0.0,
                'discount_date': format_date(self.env, term['discount_date']),
            })
            results['amount'] += term['foreign_amount']
            results['discounted_amount'] += term['discount_amount_currency']
        return amount_by_date

    @api.constrains('line_ids')
    def _check_lines(self):
        for terms in self:
            if len(terms.line_ids.filtered(lambda r: r.value == 'balance')) != 1:
                raise ValidationError(_('The Payment Term must have one Balance line.'))
            if terms.line_ids.filtered(lambda r: r.value == 'fixed' and r.discount_percentage):
                raise ValidationError(_("You can't mix fixed amount with early payment percentage"))

    def _compute_terms(self, date_ref, currency, company, tax_amount, tax_amount_currency, sign, untaxed_amount, untaxed_amount_currency):
        """Get the distribution of this payment term.
        :param date_ref: The move date to take into account
        :param currency: the move's currency
        :param company: the company issuing the move
        :param tax_amount: the signed tax amount for the move
        :param tax_amount_currency: the signed tax amount for the move in the move's currency
        :param untaxed_amount: the signed untaxed amount for the move
        :param untaxed_amount_currency: the signed untaxed amount for the move in the move's currency
        :param sign: the sign of the move
        :return (list<tuple<datetime.date,tuple<float,float>>>): the amount in the company's currency and
            the document's currency, respectively for each required payment date
        """
        self.ensure_one()
        company_currency = company.currency_id
        tax_amount_left = tax_amount
        tax_amount_currency_left = tax_amount_currency
        untaxed_amount_left = untaxed_amount
        untaxed_amount_currency_left = untaxed_amount_currency
        total_amount = tax_amount + untaxed_amount
        total_amount_currency = tax_amount_currency + untaxed_amount_currency
        result = []

        for line in self.line_ids.sorted(lambda line: line.value == 'balance'):
            term_vals = {
                'date': line._get_due_date(date_ref),
                'has_discount': line.discount_percentage,
                'discount_date': None,
                'discount_amount_currency': 0.0,
                'discount_balance': 0.0,
                'discount_percentage': line.discount_percentage,
            }

            if line.value == 'fixed':
                term_vals['company_amount'] = sign * company_currency.round(line.value_amount)
                term_vals['foreign_amount'] = sign * currency.round(line.value_amount)
                company_proportion = tax_amount/untaxed_amount if untaxed_amount else 1
                foreign_proportion = tax_amount_currency/untaxed_amount_currency if untaxed_amount_currency else 1
                line_tax_amount = company_currency.round(line.value_amount * company_proportion) * sign
                line_tax_amount_currency = currency.round(line.value_amount * foreign_proportion) * sign
                line_untaxed_amount = term_vals['company_amount'] - line_tax_amount
                line_untaxed_amount_currency = term_vals['foreign_amount'] - line_tax_amount_currency
            elif line.value == 'percent':
                term_vals['company_amount'] = company_currency.round(total_amount * (line.value_amount / 100.0))
                term_vals['foreign_amount'] = currency.round(total_amount_currency * (line.value_amount / 100.0))
                line_tax_amount = company_currency.round(tax_amount * (line.value_amount / 100.0))
                line_tax_amount_currency = currency.round(tax_amount_currency * (line.value_amount / 100.0))
                line_untaxed_amount = term_vals['company_amount'] - line_tax_amount
                line_untaxed_amount_currency = term_vals['foreign_amount'] - line_tax_amount_currency
            else:
                line_tax_amount = line_tax_amount_currency = line_untaxed_amount = line_untaxed_amount_currency = 0.0

            tax_amount_left -= line_tax_amount
            tax_amount_currency_left -= line_tax_amount_currency
            untaxed_amount_left -= line_untaxed_amount
            untaxed_amount_currency_left -= line_untaxed_amount_currency

            if line.value == 'balance':
                term_vals['company_amount'] = tax_amount_left + untaxed_amount_left
                term_vals['foreign_amount'] = tax_amount_currency_left + untaxed_amount_currency_left
                line_tax_amount = tax_amount_left
                line_tax_amount_currency = tax_amount_currency_left
                line_untaxed_amount = untaxed_amount_left
                line_untaxed_amount_currency = untaxed_amount_currency_left

            if line.discount_percentage:
                if company.early_pay_discount_computation in ('excluded', 'mixed'):
                    term_vals['discount_balance'] = company_currency.round(term_vals['company_amount'] - line_untaxed_amount * line.discount_percentage / 100.0)
                    term_vals['discount_amount_currency'] = currency.round(term_vals['foreign_amount'] - line_untaxed_amount_currency * line.discount_percentage / 100.0)
                else:
                    term_vals['discount_balance'] = company_currency.round(term_vals['company_amount'] * (1 - (line.discount_percentage / 100.0)))
                    term_vals['discount_amount_currency'] = currency.round(term_vals['foreign_amount'] * (1 - (line.discount_percentage / 100.0)))
                term_vals['discount_date'] = date_ref + relativedelta(days=line.discount_days)

            result.append(term_vals)
        return result


class AccountPaymentTermLine(models.Model):
    _inherit = "account.payment.term.line"

    months = fields.Integer(string='Months', required=True, default=0)
    end_month = fields.Boolean(string='End of month', help="Switch to end of the month after having added months or days")
    discount_percentage = fields.Float(string='Discount %', help='Early Payment Discount granted for this line')


    def _get_due_date(self, date_ref):
        self.ensure_one()
        due_date = fields.Date.from_string(date_ref)
        due_date += relativedelta(months=self.months)
        due_date += relativedelta(days=self.days)
        if self.end_month:
            due_date += relativedelta(day=31)
            due_date += relativedelta(days=self.days_after)
        return due_date


class TextBlocks(models.Model):
    _name = 'text.blocks'

    name = fields.Char('Text-block Name')
    text_block = fields.Html('Text-block Text')


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    x_studio_lieferfrist = fields.Selection(
        [
            ('ca. 6 Wochen', 'ca. 6 Wochen'),
            ('ca. 8 Wochen', 'ca. 8 Wochen'),
            ('6 - 8 Wochen', '6 - 8 Wochen'),
            ('8 - 10 Wochen', '8 - 10 Wochen'),
            ('4 Wochen', '4 Wochen'),
            ('ca. 4 Wochen, wird abgeholt in Uttigen', 'ca. 4 Wochen, wird abgeholt in Uttigen'),
            ('ca. 4 Wochen, wird geliefert', 'ca. 4 Wochen, wird geliefert'),
            ('ca. 3 bis 4 Wochen', 'ca. 3 bis 4 Wochen'),
            ('4 - 6 Wochen', '4 - 6 Wochen'),
        ]
    )
    termin = fields.Boolean(string="Show Termin")
    termin_sep = fields.Char(default="Termin")
    termin_label = fields.Char(default="Termin:")
    termin_text = fields.Text(string="Termin Text", default="nach Vereinbarung")
    abholung = fields.Boolean(string="Show Abholung")
    abholung_sep = fields.Char(default="Abholung")
    abholung_label = fields.Char(default="Abholung:")
    abholung_text = fields.Text(string="Abholung Text", default="ab Werkstatt, Uttigen")
    preise_sonderfarben = fields.Boolean(string="Show Preise Sonderfarben")
    preise_sonderfarben_sep = fields.Char(default="Preise Sonderfarben")
    preise_sonderfarben_label = fields.Char(default="Preise Sonderfarben:")
    preise_sonderfarben_text = fields.Text(string="Preise Sonderfarben Text", default="gültig 4 Wochen")
    x_studio_preise_inkl_montage = fields.Boolean(string="Show Preise inkl. Montage")
    preise_inkl_montage_sep = fields.Char(default="Preise inkl. Montage")
    preise_inkl_montage_label = fields.Char(default="Preise:")
    preise_inkl_montage_text = fields.Text(string="Preise inkl. Montage Text", default="inkl. Montage")
    preise_exkl_montage = fields.Boolean(string="Show Preise exkl. Montage")
    preise_exkl_montage_sep = fields.Char(default="Preise exkl. Montage")
    preise_exkl_montage_label = fields.Char(default="Preise:")
    preise_exkl_montage_text = fields.Text(string="Preise exkl. Montage Text", default="exkl. Montage")
    rabatt_5 = fields.Boolean(string="Show Rabatt 5%")
    rabatt_5_sep = fields.Char(default="Rabatt 5%")
    rabatt_5_label = fields.Char(default="Rabatt:")
    rabatt_5_text = fields.Text(string="Rabatt 5% Text", default="5% ab einem Bestellwert von CHF 2'000.- exkl. Sonderfarben und exkl. Reparaturen")
    rabatt_10_sep = fields.Char(default="Rabatt 10%")
    rabatt_10 = fields.Boolean(string="Show Rabatt 10%")
    rabatt_10_sep = fields.Char(default="Rabatt 10%")
    rabatt_10_label = fields.Char(default="Rabatt:")
    rabatt_10_text = fields.Text(string="Rabatt 10% Text", default="10% ab einem Bestellwert von CHF 3'000.- exkl. Sonderfarben und exkl. Reparaturen")
    rabatt_40 = fields.Boolean(string="Show Rabatt 40%")
    rabatt_40_sep = fields.Char(default="Rabatt 40%")
    rabatt_40_label = fields.Char(default="Rabatt:")
    rabatt_40_text = fields.Text(string="Rabatt 40% Text", default="40% Wiederverkaufsrabatt exkl. Sonderfarben und exkl. Montage/Reparatur")
    rabatt_u = fields.Boolean(string="Show Rabatt U")
    rabatt_u_sep = fields.Char(default="Rabatt U")
    rabatt_u_label = fields.Char(default="Rabatt:")
    rabatt_u_text = fields.Text(string="Rabatt U Text", default="5% Uttiger Rabatt bereits in Abzug gebracht")
    rabattreduktion = fields.Boolean(string="Show Rabattreduktion")
    rabattreduktion_sep = fields.Char(default="Rabattreduktion")
    rabattreduktion_label = fields.Char(default="Rabatt- Reduktion:")
    rabattreduktion_text = fields.Text(string="Rabattreduktion Text", default="Wird ein zweites Ausmass erforderlich, kann sich der Mengenrabatt reduzieren oder entfällt ganz")
    garantie = fields.Boolean(string="Show Garantie")
    garantie_sep = fields.Char(default="Garantie")
    garantie_label = fields.Char(default="Garantie:")
    garantie_text = fields.Text(string="Garantie Text", default="3 Jahre Garantie auf Material (exkl. auf Gewebe)")
    garantie_wiederverkaufer = fields.Boolean(string="Show Garantie Wiederverkäufer")
    garantie_wiederverkaufer_sep = fields.Char(default="Garantie Wiederverkäufer")
    garantie_wiederverkaufer_label = fields.Char(default="Garantie:")
    garantie_wiederverkaufer_text = fields.Text(string="Garantie Wiederverkäufer Text", default="3 Jahre Garantie auf Produkte (exkl. auf Gewebe) Schäden durch unsachgemässe Montage sind nicht garantieberechtigt")
    freier_text_block_id = fields.Many2one('text.blocks', 'Freier Text Block')
    freier_text = fields.Html('Freier Text')
    ausmessen_liefern_und_montieren = fields.Boolean(string="Ausmessen, liefern und montieren")
    ausmessen_liefern_und_montieren_text = fields.Char(string="Ausmessen, liefern und montieren", default="Ausmessen, liefern und montieren")
    reparieren_ersetzen_von = fields.Boolean(string="Reparieren / Ersetzen von")
    reparieren_ersetzen_von_text = fields.Char(string="Reparieren / Ersetzen von", default="Reparieren / Ersetzen von")
    remove_order_existing_line = fields.Boolean(string="Remove Existing Line")
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="If you change the pricelist, only newly added lines will be affected.")


    @api.onchange('freier_text_block_id')
    def onchange_freier_text_block_id(self):
        if self.freier_text_block_id:
            self.freier_text = self.freier_text_block_id.text_block


class SaleOrder(models.Model):
    _inherit = "sale.order"

    termin = fields.Boolean(string="Show Termin")
    termin_sep = fields.Char(default="Termin")
    termin_label = fields.Char(default="Termin:")
    termin_text = fields.Text(string="Termin Text", default="nach Vereinbarung")
    abholung = fields.Boolean(string="Show Abholung")
    abholung_sep = fields.Char(default="Abholung")
    abholung_label = fields.Char(default="Abholung:")
    abholung_text = fields.Text(string="Abholung Text", default="ab Werkstatt, Uttigen")
    preise_sonderfarben = fields.Boolean(string="Show Preise Sonderfarben")
    preise_sonderfarben_sep = fields.Char(default="Preise Sonderfarben")
    preise_sonderfarben_label = fields.Char(default="Preise Sonderfarben:")
    preise_sonderfarben_text = fields.Text(string="Preise Sonderfarben Text", default="gültig 4 Wochen")
    x_studio_preise_inkl_montage = fields.Boolean(string="Show Preise inkl. Montage")
    preise_inkl_montage_sep = fields.Char(default="Preise inkl. Montage")
    preise_inkl_montage_label = fields.Char(default="Preise:")
    preise_inkl_montage_text = fields.Text(string="Preise inkl. Montage Text", default="inkl. Montage")
    preise_exkl_montage = fields.Boolean(string="Show Preise exkl. Montage")
    preise_exkl_montage_sep = fields.Char(default="Preise exkl. Montage")
    preise_exkl_montage_label = fields.Char(default="Preise:")
    preise_exkl_montage_text = fields.Text(string="Preise exkl. Montage Text", default="exkl. Montage")
    rabatt_5 = fields.Boolean(string="Show Rabatt 5%")
    rabatt_5_sep = fields.Char(default="Rabatt 5%")
    rabatt_5_label = fields.Char(default="Rabatt:")
    rabatt_5_text = fields.Text(string="Rabatt 5% Text", default="5% ab einem Bestellwert von CHF 2'000.- exkl. Sonderfarben und exkl. Reparaturen")
    rabatt_10_sep = fields.Char(default="Rabatt 10%")
    rabatt_10 = fields.Boolean(string="Show Rabatt 10%")
    rabatt_10_sep = fields.Char(default="Rabatt 10%")
    rabatt_10_label = fields.Char(default="Rabatt:")
    rabatt_10_text = fields.Text(string="Rabatt 10% Text", default="10% ab einem Bestellwert von CHF 3'000.- exkl. Sonderfarben und exkl. Reparaturen")
    rabatt_40 = fields.Boolean(string="Show Rabatt 40%")
    rabatt_40_sep = fields.Char(default="Rabatt 40%")
    rabatt_40_label = fields.Char(default="Rabatt:")
    rabatt_40_text = fields.Text(string="Rabatt 40% Text", default="40% Wiederverkaufsrabatt exkl. Sonderfarben und exkl. Montage/Reparatur")
    rabatt_u = fields.Boolean(string="Show Rabatt U")
    rabatt_u_sep = fields.Char(default="Rabatt U")
    rabatt_u_label = fields.Char(default="Rabatt:")
    rabatt_u_text = fields.Text(string="Rabatt U Text", default="5% Uttiger Rabatt bereits in Abzug gebracht")
    rabattreduktion = fields.Boolean(string="Show Rabattreduktion")
    rabattreduktion_sep = fields.Char(default="Rabattreduktion")
    rabattreduktion_label = fields.Char(default="Rabatt- Reduktion:")
    rabattreduktion_text = fields.Text(string="Rabattreduktion Text", default="Wird ein zweites Ausmass erforderlich, kann sich der Mengenrabatt reduzieren oder entfällt ganz")
    garantie = fields.Boolean(string="Show Garantie")
    garantie_sep = fields.Char(default="Garantie")
    garantie_label = fields.Char(default="Garantie:")
    garantie_text = fields.Text(string="Garantie Text", default="3 Jahre Garantie auf Material (exkl. auf Gewebe)")
    garantie_wiederverkaufer = fields.Boolean(string="Show Garantie Wiederverkäufer")
    garantie_wiederverkaufer_sep = fields.Char(default="Garantie Wiederverkäufer")
    garantie_wiederverkaufer_label = fields.Char(default="Garantie:")
    garantie_wiederverkaufer_text = fields.Text(string="Garantie Wiederverkäufer Text", default="3 Jahre Garantie auf Produkte (exkl. auf Gewebe) Schäden durch unsachgemässe Montage sind nicht garantieberechtigt")
    freier_text_block_id = fields.Many2one('text.blocks', 'Freier Text Block')
    freier_text = fields.Html('Freier Text')
    ausmessen_liefern_und_montieren_text = fields.Char(string="Ausmessen, liefern und montieren", default="Ausmessen, liefern und montieren")
    reparieren_ersetzen_von_text = fields.Char(string="Reparieren / Ersetzen von", default="Reparieren / Ersetzen von")


    @api.onchange('freier_text_block_id')
    def onchange_freier_text_block_id(self):
        if self.freier_text_block_id:
            self.freier_text = self.freier_text_block_id.text_block

    def action_condition_text_add(self):
        for record in self:
            if record.termin:
                record.termin_text = "nach Vereinbarung"
            if record.abholung:
                record.abholung_text = "ab Werkstatt, Uttigen"
            if record.preise_sonderfarben:
                record.preise_sonderfarben_text = "gültig 4 Wochen"
            if record.x_studio_preise_inkl_montage:
                record.preise_inkl_montage_text = "inkl. Montage"
            if record.preise_exkl_montage:
                record.preise_exkl_montage_text = "exkl. Montage"
            if record.rabatt_5:
                record.rabatt_5_text = "5% ab einem Bestellwert von CHF 2'000.- exkl. Sonderfarben und exkl. Reparaturen"
            if record.rabatt_10:
                record.rabatt_10_text = "10% ab einem Bestellwert von CHF 3'000.- exkl. Sonderfarben und exkl. Reparaturen"
            if record.rabatt_40:
                record.rabatt_40_text = "40% Wiederverkaufsrabatt exkl. Sonderfarben und exkl. Montage/Reparatur"
            if record.rabatt_u:
                record.rabatt_u_text = "5% Uttiger Rabatt bereits in Abzug gebracht"
            if record.rabattreduktion:
                record.rabattreduktion_text = "Wird ein zweites Ausmass erforderlich, kann sich der Mengenrabatt reduzieren oder entfällt ganz"
            if record.garantie:
                record.garantie_text = "3 Jahre Garantie auf Material (exkl. auf Gewebe)"
            if record.garantie_wiederverkaufer:
                record.garantie_wiederverkaufer_text = "3 Jahre Garantie auf Produkte (exkl. auf Gewebe) Schäden durch unsachgemässe Montage sind nicht garantieberechtigt"

    @api.onchange('sale_order_template_id')
    def onchange_sale_order_template_id(self):
        #res = super(SaleOrder, self).onchange_sale_order_template_id()

        if not self.sale_order_template_id:
            self.require_signature = self._get_default_require_signature()
            self.require_payment = self._get_default_require_payment()
            return

        template = self.sale_order_template_id.with_context(lang=self.partner_id.lang)

        # --- first, process the list of products from the template
        order_lines = []
        if not self.sale_order_template_id.remove_order_existing_line:
            order_lines = []
        else:
            order_lines = [(5, 0, 0)]

        for line in template.sale_order_template_line_ids:
            data = self._compute_line_data_for_template_change(line)

            if line.product_id:
                price = line.product_id.lst_price
                discount = 0

                if self.pricelist_id:
                    pricelist_price = self.pricelist_id.with_context(uom=line.product_uom_id.id).get_product_price(line.product_id, 1, False)

                    if self.pricelist_id.discount_policy == 'without_discount' and price:
                        discount = max(0, (price - pricelist_price) * 100 / price)
                    else:
                        price = pricelist_price

                data.update({
                    'price_unit': price,
                    'discount': discount,
                    'product_uom_qty': line.product_uom_qty,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom_id.id,
                    'customer_lead': self._get_customer_lead(line.product_id.product_tmpl_id),
                })

            order_lines.append((0, 0, data))

        self.order_line = order_lines
        self.order_line._compute_tax_id()

        # then, process the list of optional products from the template
        option_lines = []
        for option in template.sale_order_template_option_ids:
            data = self._compute_option_data_for_template_change(option)
            option_lines.append((0, 0, data))

        self.sale_order_option_ids = option_lines

        if template.number_of_days > 0:
            self.validity_date = fields.Date.context_today(self) + timedelta(template.number_of_days)

        self.require_signature = template.require_signature
        self.require_payment = template.require_payment

        if not is_html_empty(template.note):
            self.note = template.note


        if self.sale_order_template_id:
            template = self.sale_order_template_id
            if template.pricelist_id:
                self.pricelist_id = template.pricelist_id.id
            self.x_studio_lieferfrist = template.x_studio_lieferfrist
            self.x_studio_preise_inkl_montage = template.x_studio_preise_inkl_montage
            if template.x_studio_preise_inkl_montage:
                self.preise_inkl_montage_text = template.preise_inkl_montage_text
                self.preise_inkl_montage_label = template.preise_inkl_montage_label
                self.preise_inkl_montage_sep = template.preise_inkl_montage_sep
            self.termin = template.termin
            if template.termin:
                self.termin_text = template.termin_text
                self.termin_label = template.termin_label
                self.termin_sep = template.termin_sep
            self.abholung = template.abholung
            if template.abholung:
                self.abholung_text = template.abholung_text
                self.abholung_label = template.abholung_label
                self.abholung_sep = template.abholung_sep
            self.preise_sonderfarben = template.preise_sonderfarben
            if template.preise_sonderfarben:
                self.preise_sonderfarben_text = template.preise_sonderfarben_text
                self.preise_sonderfarben_label = template.preise_sonderfarben_label
                self.preise_sonderfarben_sep = template.preise_sonderfarben_sep
            self.preise_exkl_montage = template.preise_exkl_montage
            if template.preise_exkl_montage:
                self.preise_exkl_montage_text = template.preise_exkl_montage_text
                self.preise_exkl_montage_label = template.preise_exkl_montage_label
                self.preise_exkl_montage_sep = template.preise_exkl_montage_sep
            self.rabatt_5 = template.rabatt_5
            if template.rabatt_5:
                self.rabatt_5_text = template.rabatt_5_text
                self.rabatt_5_label = template.rabatt_5_label
                self.rabatt_5_sep = template.rabatt_5_sep
            self.rabatt_10 = template.rabatt_10
            if template.rabatt_10:
                self.rabatt_10_text = template.rabatt_10_text
                self.rabatt_10_label = template.rabatt_10_label
                self.rabatt_10_sep = template.rabatt_10_sep
            self.rabatt_40 = template.rabatt_40
            if template.rabatt_40:
                self.rabatt_40_text = template.rabatt_40_text
                self.rabatt_40_label = template.rabatt_40_label
                self.rabatt_40_sep = template.rabatt_40_sep
            self.rabatt_u = template.rabatt_u
            if template.rabatt_u:
                self.rabatt_u_text = template.rabatt_u_text
                self.rabatt_u_label = template.rabatt_u_label
                self.rabatt_u_sep = template.rabatt_u_sep
            self.rabattreduktion = template.rabattreduktion
            if template.rabattreduktion:
                self.rabattreduktion_text = template.rabattreduktion_text
                self.rabattreduktion_label = template.rabattreduktion_label
                self.rabattreduktion_sep = template.rabattreduktion_sep
            self.garantie = template.garantie
            if template.garantie:
                self.garantie_text = template.garantie_text
                self.garantie_label = template.garantie_label
                self.garantie_sep = template.garantie_sep
            self.garantie_wiederverkaufer = template.garantie_wiederverkaufer
            if template.garantie_wiederverkaufer:
                self.garantie_wiederverkaufer_text = template.garantie_wiederverkaufer_text
                self.garantie_wiederverkaufer_label = template.garantie_wiederverkaufer_label
                self.garantie_wiederverkaufer_sep = template.garantie_wiederverkaufer_sep
            self.freier_text_block_id = template.freier_text_block_id
            self.freier_text = template.freier_text
            self.x_studio_ausmessen_liefern_und_montieren = template.ausmessen_liefern_und_montieren
            self.x_studio_reparieren_ersetzen_von = template.reparieren_ersetzen_von
        #return res

    def _create_invoices(self, grouped=False, final=False, date=None):
        res = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)
        res.x_studio_ausmessen_liefern_und_montieren = self.x_studio_ausmessen_liefern_und_montieren if self.x_studio_ausmessen_liefern_und_montieren else None
        res.ausmessen_liefern_und_montieren_text = self.ausmessen_liefern_und_montieren_text if self.ausmessen_liefern_und_montieren_text else None
        res.x_studio_reparieren_ersetzen_von = self.x_studio_reparieren_ersetzen_von if self.x_studio_reparieren_ersetzen_von else None
        res.reparieren_ersetzen_von_text = self.reparieren_ersetzen_von_text if self.reparieren_ersetzen_von_text else None
        res.garantie = self.garantie if self.garantie else None
        res.garantie_sep = self.garantie_sep if self.garantie_sep else None
        res.garantie_label = self.garantie_label if self.garantie_label else None
        res.garantie_text = self.garantie_text if self.garantie_text else None
        res.garantie_wiederverkaufer = self.garantie_wiederverkaufer if self.garantie_wiederverkaufer else None
        res.garantie_wiederverkaufer_sep = self.garantie_wiederverkaufer_sep if self.garantie_wiederverkaufer_sep else None
        res.garantie_wiederverkaufer_label = self.garantie_wiederverkaufer_label if self.garantie_wiederverkaufer_label else None
        res.garantie_wiederverkaufer_text = self.garantie_wiederverkaufer_text if self.garantie_wiederverkaufer_text else None
        res.freier_text_block_id = self.freier_text_block_id if self.freier_text_block_id else None
        res.freier_text = self.freier_text if self.freier_text else None
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.onchange('product_id')
    def product_id_change(self):
        res = super(SaleOrderLine, self).product_id_change()
        if self.product_id:
            if self.product_id.farbe:
                self.x_studio_farbe = self.product_id.farbe
            if self.product_id.grosse:
                self.x_studio_groesse = self.product_id.grosse
        return res


class AccountMove(models.Model):
    _inherit = "account.move"

    garantie = fields.Boolean(string="Show Garantie")
    garantie_sep = fields.Char(default="Garantie")
    garantie_label = fields.Char(default="Garantie:")
    garantie_text = fields.Text(string="Garantie Text", default="3 Jahre Garantie auf Material (exkl. auf Gewebe)")
    garantie_wiederverkaufer = fields.Boolean(string="Show Garantie Wiederverkäufer")
    garantie_wiederverkaufer_sep = fields.Char(default="Garantie Wiederverkäufer")
    garantie_wiederverkaufer_label = fields.Char(default="Garantie:")
    garantie_wiederverkaufer_text = fields.Text(string="Garantie Wiederverkäufer Text", default="3 Jahre Garantie auf Produkte (exkl. auf Gewebe) Schäden durch unsachgemässe Montage sind nicht garantieberechtigt")
    x_studio_ausmessen_liefern_und_montieren = fields.Boolean(string="Ausmessen, liefern und montieren")
    ausmessen_liefern_und_montieren_text = fields.Char(string="Ausmessen, liefern und montieren", default="Ausmessen, liefern und montieren")
    x_studio_reparieren_ersetzen_von = fields.Boolean(string="Reparieren / Ersetzen von")
    reparieren_ersetzen_von_text = fields.Char(string="Reparieren / Ersetzen von", default="Reparieren / Ersetzen von")
    freier_text_block_id = fields.Many2one('text.blocks', 'Freier Text Block')
    freier_text = fields.Html('Freier Text')

    payment_communication = fields.Boolean(string="Show Payment Communication")
    payment_communication_sep = fields.Char(string="Payment Communication", default="Payment Communication")
    payment_communication_text = fields.Text(string="Show Payment Communication Text", default="Bitte benutzen Sie den beigefügten QR-Einzahlungsschein für Ihre Zahlung:")

    @api.onchange('freier_text_block_id')
    def onchange_freier_text_block_id(self):
        if self.freier_text_block_id:
            self.freier_text = self.freier_text_block_id.text_block
