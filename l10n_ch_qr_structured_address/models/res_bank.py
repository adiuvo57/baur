# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
from odoo import models, _

from ..tools.address import (
    CREDITOR_BLOCK,
    MAX_NAME,
    MAX_UNSTRUCTURED_MESSAGE,
    PAYLOAD_LINES,
    ULTIMATE_DEBTOR_BLOCK,
    UNSTRUCTURED_MESSAGE_INDEX,
    sanitize_text,
    structured_address,
)


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    # ------------------------------------------------------------------
    # Address resolution
    # ------------------------------------------------------------------
    def _l10n_ch_get_structured_address(self, partner):
        """Return the SIX structured address of ``partner`` as a dict
        ``{'street', 'number', 'zip', 'city', 'source'}`` (see tools.address).

        Stored split fields (``street_name`` / ``street_number`` from
        base_address_extended or a custom module) take precedence over the
        regex parser when they are present and filled.
        """
        has_split_fields = 'street_number' in partner._fields and 'street_name' in partner._fields
        return structured_address(
            partner.street,
            partner.street2,
            partner.zip,
            partner.city,
            street_name=partner.street_name if has_split_fields else None,
            street_number=partner.street_number if has_split_fields else None,
            street_number2=partner.street_number2 if 'street_number2' in partner._fields else None,
        )

    def _l10n_ch_get_creditor_name(self):
        """Creditor name element (max 70). Hook for customer-specific rules."""
        self.ensure_one()
        return sanitize_text(self.acc_holder_name or self.partner_id.name)[:MAX_NAME]

    def _l10n_ch_get_debtor_name(self, debtor_partner):
        """Ultimate debtor name element (max 70). Hook for customer-specific
        rules (e.g. appending a second name line) – standard Odoo uses the
        commercial partner's name only, which is what is printed on the
        payment part."""
        return sanitize_text(debtor_partner.commercial_partner_id.name)[:MAX_NAME]

    def _get_partner_address_lines(self, partner):
        """Null-safe replacement of the l10n_ch helper (which crashes on a
        missing zip/city).  Only kept for API compatibility – the structured
        payload below no longer uses these combined lines."""
        addr = self._l10n_ch_get_structured_address(partner)
        line_1 = ' '.join(filter(None, (addr['street'], addr['number'])))
        line_2 = ' '.join(filter(None, (addr['zip'], addr['city'])))
        return line_1[:70], line_2[:70]

    # ------------------------------------------------------------------
    # Payload
    # ------------------------------------------------------------------
    def _l10n_ch_get_qr_vals(self, amount, currency, debtor_partner, free_communication, structured_communication):
        """Rewrite the creditor and ultimate-debtor blocks to address type "S".

        The parent (l10n_ch) keeps computing IBAN / QR-IBAN, reference type
        (QRR / SCOR / NON) and the trailer; only the address slots and the
        free-text elements are replaced, so other overrides in the MRO chain
        keep working.
        """
        vals = super()._l10n_ch_get_qr_vals(amount, currency, debtor_partner, free_communication, structured_communication)
        if len(vals) != PAYLOAD_LINES:
            # Another module changed the payload shape: do not guess positions.
            raise ValueError(
                "Unexpected Swiss QR payload shape (%s lines instead of %s); "
                "l10n_ch_qr_structured_address cannot map the address blocks." % (len(vals), PAYLOAD_LINES)
            )

        cred = self._l10n_ch_get_structured_address(self.partner_id)
        debt = self._l10n_ch_get_structured_address(debtor_partner)

        vals[CREDITOR_BLOCK] = [
            'S',                                        # Creditor Address Type
            self._l10n_ch_get_creditor_name(),          # Creditor Name
            cred['street'],                             # Creditor Street Name
            cred['number'],                             # Creditor Building Number
            cred['zip'],                                # Creditor Postal Code
            cred['city'],                               # Creditor Town
        ]
        vals[ULTIMATE_DEBTOR_BLOCK] = [
            'S',                                        # Ultimate Debtor Address Type
            self._l10n_ch_get_debtor_name(debtor_partner),
            debt['street'],                             # Ultimate Debtor Street Name
            debt['number'],                             # Ultimate Debtor Building Number
            debt['zip'],                                # Ultimate Debtor Postal Code
            debt['city'],                               # Ultimate Debtor Town
        ]
        # Unstructured message: same character rules as the address elements
        vals[UNSTRUCTURED_MESSAGE_INDEX] = sanitize_text(vals[UNSTRUCTURED_MESSAGE_INDEX])[:MAX_UNSTRUCTURED_MESSAGE]

        # A line break inside any element would shift every following payload line
        return [(v or '').replace('\r', ' ').replace('\n', ' ') for v in vals]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _l10n_ch_address_errors(self, partner, role):
        """List of human-readable problems that prevent ``partner`` from being
        emitted as a structured (type S) address."""
        errors = []
        if not partner:
            return [_("No %s partner is set.", role)]
        label = _("%(partner)s (%(role)s)", partner=partner.display_name, role=role)
        if not partner.country_id:
            errors.append(_("%s: the country is missing.", label))
        if not partner.zip:
            errors.append(_("%s: the postal code is missing.", label))
        if not partner.city:
            errors.append(_("%s: the city is missing.", label))

        addr = self._l10n_ch_get_structured_address(partner)
        if not addr['street']:
            errors.append(_("%s: the street is missing.", label))
        elif not addr['number'] and (self.company_id or self.env.company).l10n_ch_qr_require_building_number:
            errors.append(_(
                "%(label)s: the street '%(street)s' has no building number. "
                "Enter street and number together in the Street field (e.g. 'Bahnhofstrasse 12'), "
                "or put the number alone in the Street 2 field.",
                label=label, street=addr['street'],
            ))
        return errors

    def _check_for_qr_code_errors(self, qr_method, amount, currency, debtor_partner, free_communication, structured_communication):
        if qr_method == 'ch_qr':
            errors = self._l10n_ch_address_errors(self.partner_id, _("creditor"))
            if debtor_partner:
                errors += self._l10n_ch_address_errors(debtor_partner, _("debtor"))
            if errors:
                return _("The Swiss QR-bill requires a complete structured address:") + "\n- " + "\n- ".join(errors)
        return super()._check_for_qr_code_errors(qr_method, amount, currency, debtor_partner, free_communication, structured_communication)
