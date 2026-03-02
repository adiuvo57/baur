# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # Initials field originally created via Studio and used in reports.
    x_studio_initialen = fields.Char(string="Initialen")


