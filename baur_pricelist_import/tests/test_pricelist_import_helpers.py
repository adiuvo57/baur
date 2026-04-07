# -*- coding: utf-8 -*-
"""Tests that run without Odoo (pandas only).

Run from repo root (``baur``)::

    python3 -m unittest baur_pricelist_import.tests.test_pricelist_import_helpers -v

Loads helpers via importlib so the addon ``__init__`` (which imports Odoo models) is not executed.
"""
import base64
import importlib.util
import io
import os
import sys
import unittest

import pandas as pd

_HELPERS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'wizard', 'pricelist_import_helpers.py')
)
_spec = importlib.util.spec_from_file_location('pricelist_import_helpers', _HELPERS)
_helpers = importlib.util.module_from_spec(_spec)
sys.modules['pricelist_import_helpers'] = _helpers
_spec.loader.exec_module(_helpers)
detect_columns = _helpers.detect_columns
safe_float = _helpers.safe_float
safe_str = _helpers.safe_str


class TestPricelistImportHelpers(unittest.TestCase):
    def test_detect_columns_sample_headers(self):
        df = pd.DataFrame(columns=['Product Name', 'Variant Internal Reference', 'Qty', 'Price'])
        pname, ref, qty, price = detect_columns(df)
        self.assertEqual(pname, 'Product Name')
        self.assertEqual(ref, 'Variant Internal Reference')
        self.assertEqual(qty, 'Qty')
        self.assertEqual(price, 'Price')

    def test_detect_columns_alternate_headers(self):
        df = pd.DataFrame(columns=['Internal Reference', 'Min Quantity', 'Fixed Price'])
        pname, ref, qty, price = detect_columns(df)
        self.assertIsNone(pname)
        self.assertEqual(ref, 'Internal Reference')
        self.assertEqual(qty, 'Min Quantity')
        self.assertEqual(price, 'Fixed Price')

    def test_safe_str_float(self):
        self.assertEqual(safe_str('  x  '), 'x')
        self.assertEqual(safe_str(''), '')
        self.assertEqual(safe_float('12.5'), 12.5)
        self.assertEqual(safe_float(''), 0.0)
        self.assertEqual(safe_float(-1.0), -1.0)

    def test_sample_xlsx_readable(self):
        path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'static',
            'sample',
            'pricelist_import_sample.xlsx',
        )
        path = os.path.abspath(path)
        self.assertTrue(os.path.isfile(path), 'sample xlsx missing')
        df = pd.read_excel(path, sheet_name=0)
        df.columns = [str(c).strip() for c in df.columns]
        pname, ref, qty, price = detect_columns(df)
        self.assertIsNotNone(pname)
        self.assertIsNotNone(ref)
        self.assertIsNotNone(qty)
        self.assertIsNotNone(price)
        self.assertGreaterEqual(len(df), 1)

    def test_roundtrip_xlsx_base64_like_wizard(self):
        df = pd.DataFrame(
            [
                {
                    'Product Name': 'Widget A',
                    'Variant Internal Reference': 'SKU-A',
                    'Qty': 1,
                    'Price': 9.99,
                },
                {
                    'Product Name': 'Widget B',
                    'Variant Internal Reference': 'SKU-B',
                    'Qty': 10,
                    'Price': 8.0,
                },
            ]
        )
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine='openpyxl')
        raw = base64.b64encode(buf.getvalue())
        decoded = base64.b64decode(raw)
        df2 = pd.read_excel(io.BytesIO(decoded), sheet_name=0)
        df2.columns = [str(c).strip() for c in df2.columns]
        pn, r, q, p = detect_columns(df2)
        self.assertEqual(pn, 'Product Name')
        self.assertEqual(safe_str(df2.iloc[0][r]), 'SKU-A')
        self.assertEqual(safe_float(df2.iloc[0][q]), 1.0)
        self.assertEqual(safe_float(df2.iloc[0][p]), 9.99)


if __name__ == '__main__':
    unittest.main()
