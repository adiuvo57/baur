# -*- coding: utf-8 -*-
import base64
import io

import pandas as pd

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..utils import is_valid_grosse_format, parse_size_lower_bound, parse_square_meter


@tagged('post_install', '-at_install')
class TestSaleSizePricing(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Size Pricing Customer'})
        self.pricelist = self.env['product.pricelist'].create({'name': 'Size Pricing Pricelist'})

        source_template = self.env['product.template'].create({
            'name': 'Source Screen',
            'list_price': 100.0,
            'grosse': '1100x500mm',
        })
        self.source_product = source_template.product_variant_ids[0]

        addon_template = self.env['product.template'].create({
            'name': 'Addon Fabric',
            'list_price': 999.0,
            'show_in_size_pricing_popup': True,
        })
        self.addon_product = addon_template.product_variant_ids[0]
        self.addon_product.default_code = 'TTA'

        second_template = self.env['product.template'].create({
            'name': 'Second Product',
            'list_price': 50.0,
        })
        self.second_product = second_template.product_variant_ids[0]
        self.second_product.default_code = 'EV'

        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'pricelist_id': self.pricelist.id,
        })
        self.source_line = self.env['sale.order.line'].create({
            'order_id': self.order.id,
            'product_id': self.source_product.id,
            'name': self.source_product.display_name,
            'product_uom': self.source_product.uom_id.id,
            'product_uom_qty': 1.0,
            'price_unit': 100.0,
            'sequence2': 10,
        })
        self.after_line = self.env['sale.order.line'].create({
            'order_id': self.order.id,
            'product_id': self.second_product.id,
            'name': self.second_product.display_name,
            'product_uom': self.second_product.uom_id.id,
            'product_uom_qty': 1.0,
            'price_unit': 50.0,
            'sequence2': 11,
        })

    def _xlsx_b64(self, rows):
        dataframe = pd.DataFrame(rows)
        buffer = io.BytesIO()
        dataframe.to_excel(buffer, index=False, engine='openpyxl')
        return base64.b64encode(buffer.getvalue())

    def test_helper_parses_square_meter_and_ranges(self):
        self.assertTrue(is_valid_grosse_format(''))
        self.assertTrue(is_valid_grosse_format('1100x500mm'))
        self.assertFalse(is_valid_grosse_format('200 * 200 mm'))
        self.assertFalse(is_valid_grosse_format('1.75 m2'))
        self.assertAlmostEqual(parse_square_meter('1100x500mm'), 0.55, places=4)
        self.assertAlmostEqual(parse_square_meter('1100 x 500 mm'), 0.55, places=4)
        self.assertEqual(parse_square_meter('invalid'), 0.0)
        self.assertEqual(parse_size_lower_bound('< 1 m2'), 0.0)
        self.assertEqual(parse_size_lower_bound('> 1.5 - 2 m2'), 1.5)

    def test_sale_line_wizard_adds_priced_line_after_source(self):
        self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'applied_on': '0_product_variant',
            'product_id': self.addon_product.id,
            'product_tmpl_id': self.addon_product.product_tmpl_id.id,
            'min_quantity': 0.55,
            'compute_price': 'fixed',
            'fixed_price': 250.0,
        })

        wizard = self.env['sale.line.size.pricing.wizard'].create({
            'sale_order_line_id': self.source_line.id,
            'product_id': self.addon_product.id,
        })
        wizard.action_add_line()

        new_line = self.env['sale.order.line'].search([
            ('order_id', '=', self.order.id),
            ('product_id', '=', self.addon_product.id),
        ], limit=1)
        self.assertTrue(new_line)
        self.assertAlmostEqual(new_line.price_unit, 250.0, places=2)
        self.assertEqual(new_line.product_uom_qty, 1.0)

        ordered_products = self.order.order_line.sorted(key=lambda line: line.sequence2).mapped('product_id')
        self.assertEqual(ordered_products.ids, [
            self.source_product.id,
            self.addon_product.id,
            self.second_product.id,
        ])

    def test_wizard_uses_edited_square_meter_and_description(self):
        self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'applied_on': '0_product_variant',
            'product_id': self.addon_product.id,
            'product_tmpl_id': self.addon_product.product_tmpl_id.id,
            'min_quantity': 2.0,
            'compute_price': 'fixed',
            'fixed_price': 99.0,
        })

        wizard = self.env['sale.line.size.pricing.wizard'].create({
            'sale_order_line_id': self.source_line.id,
            'product_id': self.addon_product.id,
            'square_meter': 2.0,
            'description': 'Custom mesh note',
        })
        wizard.action_add_line()

        new_line = self.env['sale.order.line'].search([
            ('order_id', '=', self.order.id),
            ('product_id', '=', self.addon_product.id),
        ], limit=1)
        self.assertAlmostEqual(new_line.price_unit, 99.0, places=2)
        self.assertIn('Custom mesh note', new_line.name)

    def test_sale_line_wizard_applies_discount_on_line(self):
        self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'applied_on': '0_product_variant',
            'product_id': self.addon_product.id,
            'product_tmpl_id': self.addon_product.product_tmpl_id.id,
            'min_quantity': 0.55,
            'compute_price': 'fixed',
            'fixed_price': 200.0,
        })

        wizard = self.env['sale.line.size.pricing.wizard'].create({
            'sale_order_line_id': self.source_line.id,
            'product_id': self.addon_product.id,
            'discount': 10.0,
        })
        self.assertAlmostEqual(wizard.price_final, 180.0, places=2)
        wizard.action_add_line()

        new_line = self.env['sale.order.line'].search([
            ('order_id', '=', self.order.id),
            ('product_id', '=', self.addon_product.id),
        ], limit=1)
        self.assertAlmostEqual(new_line.price_unit, 200.0, places=2)
        self.assertAlmostEqual(new_line.discount, 10.0, places=2)
        self.assertAlmostEqual(new_line.price_subtotal, 180.0, places=2)

    def test_size_matrix_import_creates_pricelist_items(self):
        wizard = self.env['pricelist.size.matrix.import.wizard'].create({
            'pricelist_id': self.pricelist.id,
            'xlsx_file': self._xlsx_b64([
                {'Size': '< 1 m2', 'TTA': 37.0, 'EV': 20.0},
                {'Size': '> 1 - 1.5 m2', 'TTA': 54.0, 'EV': 26.0},
            ]),
        })
        wizard.action_import()

        first_rule = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pricelist.id),
            ('product_id', '=', self.addon_product.id),
            ('min_quantity', '=', 0.0),
        ], limit=1)
        second_rule = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pricelist.id),
            ('product_id', '=', self.second_product.id),
            ('min_quantity', '=', 1.0),
        ], limit=1)

        self.assertTrue(first_rule)
        self.assertTrue(second_rule)
        self.assertAlmostEqual(first_rule.fixed_price, 37.0, places=2)
        self.assertAlmostEqual(second_rule.fixed_price, 26.0, places=2)
