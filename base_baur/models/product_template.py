# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    farbe = fields.Many2one("x_farben", string="Farbe")
    grosse = fields.Char(string="Grosse")
