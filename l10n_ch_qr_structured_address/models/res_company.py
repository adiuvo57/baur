# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ch_qr_require_building_number = fields.Boolean(
        string='Swiss QR-bill: require building number',
        default=True,
        help="When enabled, a customer invoice cannot be posted, printed or sent as a "
             "Swiss QR-bill if the creditor or the debtor street has no building number "
             "(e.g. 'Industriestrasse' instead of 'Industriestrasse 12').\n"
             "SIX treats street and building number as optional elements of a structured "
             "address; this stricter check enforces complete master data.",
    )
    l10n_ch_qr_check_on_post = fields.Boolean(
        string='Swiss QR-bill: validate addresses when posting',
        default=True,
        help="When enabled, posting a customer invoice or credit note whose bank account "
             "is eligible for a Swiss QR-bill validates the creditor and debtor addresses "
             "and blocks the posting with an explicit error if they cannot be structured.\n"
             "Disable only as a temporary mitigation during data clean-up; printing and "
             "sending still validate.",
    )
