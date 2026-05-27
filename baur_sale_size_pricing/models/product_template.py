# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    show_in_size_pricing_popup = fields.Boolean(string='Show In Size Pricing Popup')
