# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Fields migrated from Odoo Studio so that reports and views work
    # without depending on Studio being installed.
    x_studio_aktuelles_datum = fields.Date(string="Aktuelles Datum")
    x_studio_char_field_tN3rU = fields.Char(string="X Studio Char Field Tn3Ru")
    x_studio_herkunft = fields.Char(string="Herkunft")
    x_studio_many2one_field_0ZRb0 = fields.Many2one(
        comodel_name="res.partner",
        string="Rechnungsadresse",
    )
    x_studio_name2 = fields.Char(string="2. Person")
    x_studio_private_phone = fields.Char(string="Private phone")
    x_studio_verwaltung = fields.Many2one(
        comodel_name="res.partner",
        string="Verwaltung",
    )
    x_studio_volumen = fields.Char(string="Volumen")
    x_studio_wegbeschreibung = fields.Text(string="Wegbeschreibung")


