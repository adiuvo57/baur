# -*- coding: utf-8 -*-
import base64
import io

import pandas as pd

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPricelistImportWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        super().setUp()
        self.pl = self.env['product.pricelist'].create({'name': 'Test PL XLSX Import'})
        tmpl = self.env['product.template'].create({
            'name': 'PL Import Test Product',
            'list_price': 100.0,
        })
        self.variant = tmpl.product_variant_ids[0]
        self.variant.default_code = 'PLIMP-UNIT-01'

    def _xlsx_b64(self, rows):
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine='openpyxl')
        return base64.b64encode(buf.getvalue())

    def test_import_creates_fixed_price_rule(self):
        wiz = self.env['pricelist.import.wizard'].create({
            'pricelist_id': self.pl.id,
            'xlsx_file': self._xlsx_b64([
                {
                    'Product Name': 'PL Import Test Product',
                    'Variant Internal Reference': 'PLIMP-UNIT-01',
                    'Qty': 1,
                    'Price': 42.5,
                },
            ]),
        })
        wiz.action_import()
        rule = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pl.id),
            ('product_id', '=', self.variant.id),
            ('min_quantity', '=', 1.0),
        ])
        self.assertEqual(len(rule), 1)
        self.assertEqual(rule.applied_on, '0_product_variant')
        self.assertEqual(rule.compute_price, 'fixed')
        self.assertAlmostEqual(rule.fixed_price, 42.5, places=2)

    def test_import_updates_existing_rule(self):
        self.env['product.pricelist.item'].create({
            'pricelist_id': self.pl.id,
            'applied_on': '0_product_variant',
            'product_id': self.variant.id,
            'product_tmpl_id': self.variant.product_tmpl_id.id,
            'min_quantity': 5.0,
            'compute_price': 'fixed',
            'fixed_price': 1.0,
        })
        wiz = self.env['pricelist.import.wizard'].create({
            'pricelist_id': self.pl.id,
            'xlsx_file': self._xlsx_b64([
                {
                    'Product Name': 'PL Import Test Product',
                    'Variant Internal Reference': 'PLIMP-UNIT-01',
                    'Qty': 5,
                    'Price': 77.0,
                },
            ]),
        })
        wiz.action_import()
        rule = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', self.pl.id),
            ('product_id', '=', self.variant.id),
            ('min_quantity', '=', 5.0),
        ])
        self.assertEqual(len(rule), 1)
        self.assertAlmostEqual(rule.fixed_price, 77.0, places=2)

    def test_import_errors_on_negative_qty(self):
        wiz = self.env['pricelist.import.wizard'].create({
            'pricelist_id': self.pl.id,
            'xlsx_file': self._xlsx_b64([
                {'Variant Internal Reference': 'PLIMP-UNIT-01', 'Qty': -1, 'Price': 10.0},
            ]),
        })
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            wiz.action_import()

    def test_import_errors_on_product_name_mismatch(self):
        wiz = self.env['pricelist.import.wizard'].create({
            'pricelist_id': self.pl.id,
            'xlsx_file': self._xlsx_b64([
                {
                    'Product Name': 'Wrong Name',
                    'Variant Internal Reference': 'PLIMP-UNIT-01',
                    'Qty': 1,
                    'Price': 10.0,
                },
            ]),
        })
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            wiz.action_import()
