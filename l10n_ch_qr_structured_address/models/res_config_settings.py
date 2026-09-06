# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ch_qr_require_building_number = fields.Boolean(
        related='company_id.l10n_ch_qr_require_building_number', readonly=False)
    l10n_ch_qr_check_on_post = fields.Boolean(
        related='company_id.l10n_ch_qr_check_on_post', readonly=False)
