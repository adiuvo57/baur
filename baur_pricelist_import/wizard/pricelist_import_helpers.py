# -*- coding: utf-8 -*-
"""Pure helpers for XLSX pricelist import (no Odoo imports)."""

from datetime import datetime

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


def parse_datetime(val, end_of_day=False):
    """Parse Excel / string dates into a naive datetime, or None if empty/invalid.

    Odoo requires ``date_end`` > ``date_start`` when both are set. For the **end** column,
    a date-only value (midnight) is shifted to end-of-day so a same-day range is valid.
    """
    if pd is None:
        return None
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        if pd.isna(val):
            return None
    except TypeError:
        pass
    if isinstance(val, datetime):
        dt = val
    else:
        try:
            ts = pd.to_datetime(val, errors='coerce')
        except Exception:
            return None
        if pd.isna(ts):
            return None
        try:
            dt = ts.to_pydatetime()
        except Exception:
            return None
    if end_of_day and dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def detect_columns(df):
    """Resolve column names: optional product name, ref, qty, price, start/end dates."""
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

    date_start = pick_exact(
        'start date',
        'date start',
        'valid from',
    ) or pick_substring('start date')

    date_end = pick_exact(
        'end date',
        'date end',
        'valid to',
    ) or pick_substring('end date')

    return product_name, ref, qty, price, date_start, date_end
