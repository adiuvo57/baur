# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
from odoo import fields, models, api


# class Farben(models.Model):
#     """Technical model equivalent to the Studio model 'x_farben'.

#     This replaces the Studio customization with a proper Python model so the
#     fields are available in all databases without relying on Studio.
#     """

#     _name = "x_farben"
#     _description = "Farben"
#     _order = "x_studio_sequence asc, id asc"

#     x_active = fields.Boolean(string="Aktiv", default=True)
#     x_name = fields.Char(string="Farbcode")
#     x_studio_attribute_value = fields.Many2one(
#         comodel_name="product.attribute.value",
#         string="Attribute Value",
#     )
#     x_studio_attribute_value_2 = fields.Many2one(
#         comodel_name="product.attribute.value",
#         string="Attribute Value",
#     )
#     x_studio_bezeichnung = fields.Char(string="Bezeichnung")
#     x_studio_notes = fields.Text(string="Notizen")
#     x_studio_sequence = fields.Integer(string="Reihenfolge", default=10)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    farbe = fields.Many2one("x_farben", string="Farbe")
    grosse = fields.Char(string="Grosse")
