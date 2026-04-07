# -*- coding: utf-8 -*-
"""Pure helpers for XLSX pricelist import (no Odoo imports)."""

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


def safe_float(val):
    try:
        if pd is not None and pd.isna(val):
            return 0.0
        f = float(val)
        return 0.0 if str(val).strip() == '' else f
    except (ValueError, TypeError):
        return 0.0


def safe_str(val):
    try:
        if pd is not None and pd.isna(val):
            return ''
        if val is None or str(val).strip() in ('', 'nan'):
            return ''
        return str(val).strip()
    except (ValueError, TypeError):
        return ''


def normalize_header(h):
    return str(h).strip().lower().replace('_', ' ')


def detect_columns(df):
    """Resolve column names: optional product name, variant reference, quantity, price."""
    norm_to_orig = {normalize_header(c): c for c in df.columns}

    def pick_exact(*labels):
        for lab in labels:
            key = normalize_header(lab)
            if key in norm_to_orig:
                return norm_to_orig[key]
        return None

    def pick_substring(*needles):
        for needle in needles:
            n = needle.lower()
            for nk, orig in norm_to_orig.items():
                if n in nk:
                    return orig
        return None

    product_name = pick_exact('product name') or pick_substring('product name')

    ref = pick_exact(
        'variant internal reference',
        'internal reference',
        'default code',
        'sku',
    ) or pick_substring('internal reference', 'default code')

    qty = pick_exact(
        'qty',
        'quantity',
        'min quantity',
        'min. quantity',
        'min_qty',
    ) or pick_substring('min quantity', 'qty')

    price = pick_exact(
        'price',
        'fixed price',
        'fixed_price',
        'amount',
        'unit price',
    ) or pick_substring('fixed price')

    return product_name, ref, qty, price
