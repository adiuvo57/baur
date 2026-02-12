# -*- coding: utf-8 -*-
"""Import logic for product template wizard - extracted to keep wizard file slim."""
import base64
import io
import csv
import logging
from datetime import datetime

import pandas as pd
import requests

from odoo import _, tools
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

ATTR_COLS = [
    'Size', 'Colour', 'Flavor', 'Scent', 'Unit',
    'Cm', 'Inches', 'ft', 'oz', 'KG / g', 'L / ml',
    'Type', 'Brand', 'Manufacturer', 'Grosse', 'Grösse',
]
VARIANT_ATTRS = ['Size', 'Colour', 'Type', 'KG / g', 'Brand', 'Grosse', 'Grösse']


def safe_float(val):
    try:
        f = float(val)
        return 0.0 if (pd.isna(f) or str(val).strip() == '') else f
    except (ValueError, TypeError):
        return 0.0


def safe_str(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() in ('', 'nan'):
            return ''
        return str(val).strip()
    except (ValueError, TypeError):
        return ''


class ImportLogic:
    """Handles standard product import and HTML-only import."""

    def __init__(self, env):
        self.env = env

    def run_standard(self, df, wizard_model, wizard_id):
        """Run full product import. Returns action dict."""
        return _process_data(self.env, df, wizard_model, wizard_id)


def _get_or_create_attr(env, name, create_variant='always'):
    m = env['product.attribute']
    attr = m.search([('name', '=', name)], limit=1)
    if not attr:
        try:
            attr = m.create({'name': name, 'create_variant': create_variant})
        except Exception:
            attr = m.create({'name': name})
    return attr


def _get_or_create_attr_value(env, attribute, value_name):
    if not value_name or not value_name.strip():
        return False
    m = env['product.attribute.value']
    v = m.search([('attribute_id', '=', attribute.id), ('name', '=', value_name.strip())], limit=1)
    if not v:
        v = m.create({'name': value_name.strip(), 'attribute_id': attribute.id})
    return v


def _get_or_create_expense_account_4200(env):
    """Find or create a default expense account with code 4200."""
    Account = env['account.account']
    # Try to find existing 4200 account
    acc = Account.search([('code', '=', '4200')], limit=1)
    if acc:
        return acc

    # Determine expense account type
    expense_type = None
    try:
        expense_type = env.ref('account.data_account_type_expenses', raise_if_not_found=False)
    except Exception:
        expense_type = None
    if not expense_type:
        expense_type = env['account.account.type'].search([('type', '=', 'expense')], limit=1)

    vals = {
        'code': '4200',
        'name': '4200 Expense',
        'company_id': env.company.id,
    }
    if 'user_type_id' in Account._fields and expense_type:
        vals['user_type_id'] = expense_type.id
    elif 'account_type' in Account._fields:
        vals['account_type'] = 'expense'

    try:
        return Account.create(vals)
    except Exception as e:
        _logger.warning("Could not create expense account 4200: %s", e)
        return acc

def _get_or_create_income_account(env, label):
    """Find or create an income account by label (name/code)."""
    name = safe_str(label)
    if not name:
        return False
    Account = env['account.account']
    # Try to match by code (first token) or full name
    first_token = name.split()[0]
    domain = ['|', ('code', '=', first_token), ('name', '=', name)]
    acc = Account.search(domain, limit=1)
    if acc:
        return acc

    # Determine income account type depending on version/fields
    income_type = None
    try:
        income_type = env.ref('account.data_account_type_revenue', raise_if_not_found=False)
    except Exception:
        income_type = None
    if not income_type:
        try:
            income_type = env.ref('account.data_account_type_other_income', raise_if_not_found=False)
        except Exception:
            income_type = None
    if not income_type:
        income_type = env['account.account.type'].search([('type', '=', 'income')], limit=1)

    vals = {
        'code': first_token,
        'name': name,
        'company_id': env.company.id,
    }
    # Handle both legacy user_type_id and newer account_type API
    if 'user_type_id' in Account._fields and income_type:
        vals['user_type_id'] = income_type.id
    elif 'account_type' in Account._fields:
        vals['account_type'] = 'income'

    try:
        return Account.create(vals)
    except Exception as e:
        _logger.warning("Could not create income account '%s': %s", name, e)
        return False

def _download_image(env, url):
    url = safe_str(url)
    if not url:
        return False
    lower = url.lower()
    if any(lower.endswith(e) for e in ('.jpg', '.jpeg', '.png', '.gif', '.webp')) or '.' not in url.rsplit('/', 1)[-1]:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            if 'image' not in (r.headers.get('Content-Type') or '').lower():
                return False
            proc = tools.image_process(r.content) if hasattr(tools, 'image_process') else r.content
            return base64.b64encode(proc)
        except Exception as e:
            _logger.warning("Could not download image %s: %s", url, e)
    return False


def _process_images(env, product, row):
    cols = [c for c in row.index if 'image' in safe_str(c).lower()]
    if not cols or not product:
        return
    ProductImage = env['product.image']
    main_set = bool(product.image_1920)
    for col in cols:
        url = safe_str(row.get(col) or '')
        if not url:
            continue
        b64 = _download_image(env, url)
        if not b64:
            continue
        try:
            if not main_set:
                product.write({'image_1920': b64})
                main_set = True
            else:
                ProductImage.create({'name': product.name, 'product_tmpl_id': product.id, 'image_1920': b64})
        except Exception as e:
            _logger.warning("Image error %s: %s", col, e)


def _process_variants(env, product, group_df, variant_attrs, main_ref_col, variant_ref_col, ean_col, combo_ean_col, attr_attrvalue_col):
    """Update variants (barcode, SKU, cost/sales price) and create pricelist
    items per variant (min qty = 1) using the sales price from the row."""
    ProductProduct = env['product.product']
    Pricelist = env['product.pricelist']
    PricelistItem = env['product.pricelist.item']
    name = product.name

    # Default pricelist (Public Pricelist) or first available one
    default_pricelist = env.ref("product.list0", raise_if_not_found=False) or Pricelist.search([], limit=1)
    for idx, row in group_df.iterrows():
        try:
            base_sku = safe_str(row.get('Product ID') or row.get('SKU') or '')
            main_ref = safe_str(row.get(main_ref_col)) if main_ref_col else ''
            variant_ref = safe_str(row.get(variant_ref_col)) if variant_ref_col else ''
            variant_sku = variant_ref or base_sku or main_ref or ''
            combo = safe_str(row.get(combo_ean_col)) if combo_ean_col else ''
            ean = safe_str(row.get(ean_col)) if ean_col else ''
            leg = safe_str(row.get('Item Number') or row.get('Barcode') or '')
            variant_barcode = combo or leg or ean
            cost = safe_str(row.get('Cost Price') or '')
            sales = safe_str(row.get('Selling Price') or row.get('Sales Price') or '')
            attrs = {}
            for ac in variant_attrs:
                v = safe_str(row.get(ac) or '')
                if v:
                    attrs[ac] = v
            if attr_attrvalue_col:
                raw = safe_str(row.get(attr_attrvalue_col) or '')
                if raw and ':' in raw:
                    a, b = raw.split(':', 1)
                    if (a or '').strip() and (b or '').strip():
                        attrs[(a or '').strip()] = (b or '').strip()
            variant = None
            if attrs:
                all_v = ProductProduct.search([('product_tmpl_id.name', '=', name)])
                for var in all_v:
                    ok = True
                    for attr_col, exp in attrs.items():
                        found = any(
                            tav.attribute_id.name == attr_col and tav.product_attribute_value_id.name.strip() == exp.strip()
                            for tav in var.product_template_attribute_value_ids
                        )
                        if not found:
                            ok = False
                            break
                    if ok:
                        variant = var
                        break
            if not variant and variant_barcode:
                variant = ProductProduct.search([('product_tmpl_id.name', '=', name), ('barcode', '=', variant_barcode)], limit=1)
            if not variant and variant_sku:
                variant = ProductProduct.search([('product_tmpl_id.name', '=', name), ('default_code', '=', variant_sku)], limit=1)
            if not variant:
                cnt = ProductProduct.search_count([('product_tmpl_id.name', '=', name)])
                if cnt == 1 or not attrs:
                    variant = ProductProduct.search([('product_tmpl_id.name', '=', name)], limit=1)
            if variant:
                vals = {}
                if variant_barcode:
                    vals['barcode'] = variant_barcode
                if variant_sku:
                    vals['default_code'] = variant_sku
                if cost and safe_float(cost) > 0:
                    vals['standard_price'] = safe_float(cost)
                if sales and safe_float(sales) > 0:
                    vals['list_price'] = safe_float(sales)
                if vals:
                    variant.write(vals)

                # Create / update variant-wise pricelist item (min qty = 1)
                if default_pricelist and sales and safe_float(sales) > 0:
                    price_fixed = safe_float(sales)
                    item = PricelistItem.search(
                        [
                            ("pricelist_id", "=", default_pricelist.id),
                            ("applied_on", "=", "0_product_variant"),
                            ("product_id", "=", variant.id),
                            ("min_quantity", "=", 1),
                        ],
                        limit=1,
                    )
                    vals_item = {
                        "pricelist_id": default_pricelist.id,
                        "applied_on": "0_product_variant",
                        "product_id": variant.id,
                        "min_quantity": 1,
                        "fixed_price": price_fixed,
                    }
                    if item:
                        item.write({"fixed_price": price_fixed})
                    else:
                        PricelistItem.create(vals_item)
        except Exception as e:
            _logger.warning("Variant row %s: %s", idx, e)


def _process_data(env, df, wizard_model, wizard_id):
    ProductTemplate = env['product.template']
    ProductCategory = env['product.category']
    SupplierInfo = env['product.supplierinfo']
    failed = []
    # Default expense account 4200 (created if needed)
    expense_account = _get_or_create_expense_account_4200(env)
    df.columns = [str(c).strip() for c in df.columns]
    attr_cols = list(ATTR_COLS)
    variant_attrs = list(VARIANT_ATTRS)
    main_ref = variant_ref = ean_col = combo_ean = product_name_col = cost_col = sales_col = attr_attrvalue_col = income_account_col = None
    for col in df.columns:
        c, l = str(col).strip(), str(col).strip().lower()
        if not main_ref and ('reference main product' in l or 'produkt-referenzcode' in l or c == 'new_code'):
            main_ref = col
        if not variant_ref and ('reference of variants' in l or 'referenzcode der kombinationen' in l or 'internal reference' in l):
            variant_ref = col
        if not combo_ean and 'kombinat' in l and 'barcode' in l:
            combo_ean = col
        if not ean_col and 'ean-13' in l and 'barcode' in l:
            ean_col = col
        if not product_name_col and ('product name' in l or 'produktname' in l or c == 'Name'):
            product_name_col = col
        if not cost_col and ('cost price' in l or 'purchase price' in l or 'einkaufspreis' in l):
            cost_col = col
        if not sales_col and ('sales price' in l or ('endpreis' in l and 'steuer' in l)):
            sales_col = col
        if 'attribute group_' in l or 'brand' in l or 'herstellername' in l:
            if c not in attr_cols:
                attr_cols.append(c)
            if c not in variant_attrs:
                variant_attrs.append(c)
        if not attr_attrvalue_col and 'attribute' in l and ('attributvalue' in l or ('attribut' in l and 'value' in l)):
            attr_attrvalue_col = col
        if not income_account_col and 'income account' in l:
            income_account_col = col
    group_col = main_ref or ('new_code' if 'new_code' in df.columns else None) or ('Internal Reference' if 'Internal Reference' in df.columns else None)
    if not group_col:
        if 'Product ID' in df.columns:
            def _gk(r):
                pid = r.get('Product ID')
                if pd.notna(pid) and str(pid or '').strip():
                    return str(pid).strip()
                return str(r.get('Item Name') or r.get('Name') or '').strip() or '_no_name'
            df['_gk'] = df.apply(_gk, axis=1)
            group_col = '_gk'
        else:
            group_col = 'Counter' if 'Counter' in df.columns else 'Item Name' if 'Item Name' in df.columns else 'Name' if 'Name' in df.columns else '_idx'
            if group_col == '_idx':
                df['_idx'] = range(len(df))
    for gk, gdf in df.groupby(group_col):
        row = gdf.iloc[0].copy()
        orig = row.to_dict()
        avd = {ac: set() for ac in attr_cols}
        for idx, r in gdf.iterrows():
            for ac in attr_cols:
                v = safe_str(r.get(ac) or '')
                if v:
                    avd[ac].add(v)
        avp = {}
        if attr_attrvalue_col:
            for idx, r in gdf.iterrows():
                raw = safe_str(r.get(attr_attrvalue_col) or '')
                if raw and ':' in raw:
                    a, b = raw.split(':', 1)
                    if (a or '').strip() and (b or '').strip():
                        avp.setdefault((a or '').strip(), set()).add((b or '').strip())
        try:
            with env.cr.savepoint():
                name = safe_str(row.get('Item Name') or row.get('Name') or (product_name_col and row.get(product_name_col)) or '')
                if not name:
                    continue
                barcode = safe_str(row.get(ean_col) or '') if ean_col else ''
                if not barcode:
                    barcode = safe_str(row.get('Item Number') or row.get('Barcode') or '')
                cost = safe_str(row.get(cost_col) or '') if cost_col else safe_str(row.get('Cost Price') or '')
                sales = safe_str(row.get(sales_col) or '') if sales_col else safe_str(row.get('Selling Price') or '')
                # Internal reference on template: prefer explicit new_code column
                new_code_val = safe_str(row.get('new_code') or '')
                mrv = safe_str(row.get(main_ref)) if main_ref else ''
                dc = new_code_val or safe_str(row.get('Product ID') or row.get('SKU') or '')
                if not dc and mrv:
                    dc = mrv
                if not dc and barcode:
                    dc = barcode
                cat = safe_str(row.get('Category') or row.get('Productcategory') or '')
                # Income account (optional)
                income_account = False
                if income_account_col:
                    income_label = safe_str(row.get(income_account_col) or '')
                    if income_label:
                        income_account = _get_or_create_income_account(env, income_label)
                parent = False
                for categ in [c.strip() for c in cat.replace('|', '/').split('/') if c.strip()]:
                    if not categ.strip():
                        continue
                    pc = parent
                    parent = ProductCategory.search([('name', '=', categ), ('parent_id', '=', pc.id if pc else False)], limit=1)
                    if not parent and categ:
                        parent = ProductCategory.create({'name': categ, 'parent_id': pc.id if pc else False})
                if not parent:
                    try:
                        parent = env.ref('product.product_category_all', raise_if_not_found=False)
                    except Exception:
                        parent = ProductCategory.search([], limit=1)
                disc = safe_str(row.get('Description') or '')
                longd = safe_str(row.get('Long Description') or '')
                # Grosse column value (store also on template field if it exists)
                grosse_val = safe_str(row.get('Grosse') or row.get('Grösse') or '')
                # Find existing template primarily by internal reference (default_code),
                # so that each distinct new_code becomes its own product.
                if dc:
                    product = ProductTemplate.search([('default_code', '=', dc)], limit=1)
                else:
                    product = ProductTemplate.search([('name', '=', name)], limit=1)
                if not product:
                    default_categ = env.ref('product.product_category_all', raise_if_not_found=False) or ProductCategory.search([], limit=1)
                    vals = {
                        'name': name,
                        'categ_id': (parent or default_categ).id,
                        'barcode': barcode or False,
                        'standard_price': safe_float(cost),
                        'list_price': safe_float(sales),
                        'default_code': dc or False,
                        'type': 'product',
                        'description': disc or False,
                    }
                    if income_account and 'property_account_income_id' in ProductTemplate._fields:
                        vals['property_account_income_id'] = income_account.id
                    if expense_account and 'property_account_expense_id' in ProductTemplate._fields:
                        vals['property_account_expense_id'] = expense_account.id
                    if grosse_val and 'grosse' in ProductTemplate._fields:
                        vals['grosse'] = grosse_val
                    product = ProductTemplate.create(vals)

                # For both new and existing products, update accounts / grosse if provided.
                if product:
                    write_vals = {}
                    if income_account and 'property_account_income_id' in ProductTemplate._fields:
                        write_vals['property_account_income_id'] = income_account.id
                    if expense_account and 'property_account_expense_id' in ProductTemplate._fields:
                        write_vals['property_account_expense_id'] = expense_account.id
                    if grosse_val and 'grosse' in ProductTemplate._fields:
                        write_vals['grosse'] = grosse_val
                    if write_vals:
                        product.write(write_vals)
                _process_images(env, product, row)
                existing = {l.attribute_id.id: l for l in product.attribute_line_ids}
                to_add = []
                for ac in attr_cols:
                    vs = avd.get(ac, set())
                    if not vs:
                        continue
                    attr = _get_or_create_attr(env, ac, 'always' if ac in variant_attrs else 'no_variant')
                    ids = []
                    for v in vs:
                        av = _get_or_create_attr_value(env, attr, v)
                        if av:
                            ids.append(av.id)
                    if ids:
                        if attr.id in existing:
                            line = existing[attr.id]
                            line.write({'value_ids': [(6, 0, list(set(line.value_ids.ids + ids)))]})
                        else:
                            to_add.append((0, 0, {'attribute_id': attr.id, 'value_ids': [(6, 0, ids)]}))
                for aname, vs in avp.items():
                    if not vs:
                        continue
                    attr = _get_or_create_attr(env, aname, 'always')
                    ids = []
                    for v in vs:
                        av = _get_or_create_attr_value(env, attr, v)
                        if av:
                            ids.append(av.id)
                    if ids:
                        if attr.id in existing:
                            line = existing[attr.id]
                            line.write({'value_ids': [(6, 0, list(set(line.value_ids.ids + ids)))]})
                        else:
                            to_add.append((0, 0, {'attribute_id': attr.id, 'value_ids': [(6, 0, ids)]}))
                if to_add:
                    product.write({'attribute_line_ids': to_add})
                _process_variants(env, product, gdf, variant_attrs, main_ref, variant_ref, ean_col, combo_ean, attr_attrvalue_col)
                sup = safe_str(row.get('Supplier Id') or '')
                if sup and not SupplierInfo.search([('product_tmpl_id', '=', product.id)], limit=1):
                    p = env['res.partner'].search([('name', '=', sup)], limit=1)
                    if p:
                        SupplierInfo.create({'partner_id': p.id, 'product_tmpl_id': product.id})
        except Exception as e:
            _logger.error("Product error %s: %s", name if 'name' in dir() else gk, e)
            failed.append({'row_data': orig, 'row_series': row, 'error': str(e)})
    if failed:
        return _bounce_file(env, failed, df.columns.tolist(), wizard_model, wizard_id)
    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _('Success'), 'message': _('All products imported successfully!'), 'type': 'success', 'sticky': False}}


def _bounce_file(env, failed, cols, wizard_model, wizard_id):
    try:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['=' * 80])
        w.writerow(['PRODUCT IMPORT FAILURE REPORT'])
        w.writerow(['=' * 80])
        w.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        w.writerow(['Failed:', len(failed)])
        headers = list(cols) + ['>>> ERROR <<<']
        w.writerow(headers)
        for fp in failed:
            row = fp.get('row_series')
            data = fp.get('row_data', {})
            err = fp.get('error', '')
            vals = []
            for c in cols:
                v = row[c] if row is not None and c in getattr(row, 'index', []) else data.get(c, '')
                vals.append(safe_str(v))
            w.writerow(vals + [f'>>> {err} <<<'])
        att = env['ir.attachment'].create({
            'name': f'Failed_Import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'type': 'binary', 'datas': base64.b64encode(out.getvalue().encode('utf-8')),
            'mimetype': 'text/csv', 'res_model': wizard_model, 'res_id': wizard_id,
        })
        return {'type': 'ir.actions.act_url', 'url': f'/web/content/{att.id}?download=true', 'target': 'self'}
    except Exception as e:
        _logger.error("Bounce file error: %s", e)
        raise UserError(_("Error generating bounce file: %s") % str(e))



