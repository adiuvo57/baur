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

    def run_html_only(self, file_data):
        """Run HTML descriptions + pricelist update. Returns action dict."""
        try:
            decoded = base64.b64decode(file_data or b"")
        except Exception as e:
            raise ValidationError(_("Error reading XLSX file: %s") % str(e))
        try:
            buf = io.BytesIO(decoded)
            xls = pd.ExcelFile(buf)
            sheets = [str(s).strip() for s in xls.sheet_names]
            if not sheets:
                raise ValidationError(_("The uploaded XLSX file does not contain any worksheets."))
            buf.seek(0)
            df = pd.read_excel(buf, sheet_name=sheets[0], skiprows=0)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_("Error reading XLSX workbook: %s") % str(e))
        return _process_html_descriptions(self.env, df)


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
    ProductProduct = env['product.product']
    name = product.name
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
        except Exception as e:
            _logger.warning("Variant row %s: %s", idx, e)


def _process_data(env, df, wizard_model, wizard_id):
    ProductTemplate = env['product.template']
    ProductCategory = env['product.category']
    PublicCategory = env['product.public.category']
    SupplierInfo = env['product.supplierinfo']
    failed = []
    df.columns = [str(c).strip() for c in df.columns]
    attr_cols = list(ATTR_COLS)
    variant_attrs = list(VARIANT_ATTRS)
    main_ref = variant_ref = ean_col = combo_ean = product_name_col = cost_col = sales_col = attr_attrvalue_col = None
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
        for _, r in gdf.iterrows():
            for ac in attr_cols:
                v = safe_str(r.get(ac) or '')
                if v:
                    avd[ac].add(v)
        avp = {}
        if attr_attrvalue_col:
            for _, r in gdf.iterrows():
                raw = safe_str(r.get(attr_attrvalue_col) or '')
                if raw and ':' in raw:
                    a, b = raw.split(':', 1)
                    if (a or '').strip() and (b or '').strip():
                        avp.setdefault((a or '').strip(), set()).add((b or '').strip())
        try:
            name = safe_str(row.get('Item Name') or row.get('Name') or (product_name_col and row.get(product_name_col)) or '')
            if not name:
                continue
            barcode = safe_str(row.get(ean_col) or '') if ean_col else ''
            if not barcode:
                barcode = safe_str(row.get('Item Number') or row.get('Barcode') or '')
            cost = safe_str(row.get(cost_col) or '') if cost_col else safe_str(row.get('Cost Price') or '')
            sales = safe_str(row.get(sales_col) or '') if sales_col else safe_str(row.get('Selling Price') or '')
            mrv = safe_str(row.get(main_ref)) if main_ref else ''
            dc = safe_str(row.get('Product ID') or row.get('SKU') or '')
            if not dc and mrv:
                dc = mrv
            if not dc and barcode:
                dc = barcode
            cat = safe_str(row.get('Category') or '')
            parent = public_parent = False
            for categ in cat.split("|"):
                if not categ.strip():
                    continue
                pc = parent
                parent = ProductCategory.search([('name', '=', categ), ('parent_id', '=', pc.id if pc else False)], limit=1)
                if not parent and categ:
                    parent = ProductCategory.create({'name': categ, 'parent_id': pc.id if pc else False})
                ppc = public_parent
                public_parent = PublicCategory.search([('name', '=', categ), ('parent_id', '=', ppc.id if ppc else False)], limit=1)
                if not public_parent and categ:
                    public_parent = PublicCategory.create({'name': categ, 'parent_id': ppc.id if ppc else False})
            disc = safe_str(row.get('Description') or '')
            longd = safe_str(row.get('Long Description') or '')
            tags = []
            for t in (safe_str(row.get('Tags') or '')).split(','):
                t = t.strip()
                if t:
                    tg = env['product.tag'].search([('name', '=', t)], limit=1)
                    if not tg:
                        tg = env['product.tag'].create({'name': t})
                    tags.append(tg.id)
            product = ProductTemplate.search([('name', '=', name)], limit=1)
            if not product:
                vals = {
                    'name': name, 'categ_id': parent.id if parent else False, 'barcode': barcode or False,
                    'standard_price': safe_float(cost), 'list_price': safe_float(sales),
                    'default_code': dc or False, 'type': 'consu', 'description': disc or False,
                }
                if public_parent:
                    vals['public_categ_ids'] = [(6, 0, [public_parent.id])]
                if longd or disc:
                    try:
                        if 'description_ecommerce' in ProductTemplate._fields:
                            vals['description_ecommerce'] = longd or disc
                    except Exception:
                        pass
                if tags and 'product_tag_ids' in ProductTemplate._fields:
                    vals['product_tag_ids'] = [(6, 0, tags)]
                product = ProductTemplate.create(vals)
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


def _process_html_descriptions(env, df):
    ProductTemplate = env['product.template']
    ProductProduct = env['product.product']
    PricelistItem = env['product.pricelist.item']
    df.columns = [str(c).strip() for c in df.columns]
    main_ref = variant_ref = ean_col = combo_ean = sales_col = None
    for col in df.columns:
        l = str(col).strip().lower()
        if not main_ref and ('reference main product' in l or 'produkt-referenzcode' in l):
            main_ref = col
        if not ean_col and 'ean-13' in l and 'barcode' in l:
            ean_col = col
        if not variant_ref and ('reference of variants' in l or 'referenzcode der kombinationen' in l):
            variant_ref = col
        if not combo_ean and 'kombinat' in l and 'barcode' in l:
            combo_ean = col
        if not sales_col and ('sales price' in l or ('endpreis' in l and 'steuer' in l)):
            sales_col = col
    cols = list(df.columns)
    if len(cols) <= 8:
        raise ValidationError(_("XLSX needs at least columns H and I (description_ecommerce, website_description)."))
    desc_col, web_col = cols[7], cols[8]
    pricelist = env.ref("product.list0", raise_if_not_found=False) or env['product.pricelist'].search([], limit=1)
    updated = not_found = 0
    for idx, row in df.iterrows():
        try:
            mrv = safe_str(row.get(main_ref)) if main_ref else ''
            dc = safe_str(row.get("Product ID") or row.get("SKU") or "")
            if not dc and mrv:
                dc = mrv
            bc = safe_str(row.get(ean_col) or "") if ean_col else ""
            if not bc:
                bc = safe_str(row.get("EAN-13 oder JAN-Barcode") or row.get("Barcode") or row.get("EAN-13 Barcode") or "")
            vref = safe_str(row.get(variant_ref)) if variant_ref else ""
            vdc = vref or safe_str(row.get("Product ID") or row.get("SKU") or "") or mrv or ""
            combo = safe_str(row.get(combo_ean)) if combo_ean else ""
            leg = safe_str(row.get("Item Number") or row.get("Barcode") or "")
            ean = safe_str(row.get(ean_col)) if ean_col else ""
            vbc = combo or leg or ean
            if not dc and not bc and not vdc and not vbc:
                continue
            product = variant = None
            if dc or bc:
                d = [("default_code", "=", dc), ("barcode", "=", bc)] if dc and bc else [("default_code", "=", dc)] if dc else [("barcode", "=", bc)]
                product = ProductTemplate.search(d if len(d) == 1 else ["|"] + d, limit=1)
            if vdc or vbc:
                d = [("default_code", "=", vdc), ("barcode", "=", vbc)] if vdc and vbc else [("default_code", "=", vdc)] if vdc else [("barcode", "=", vbc)]
                variant = ProductProduct.search(d if len(d) == 1 else ["|"] + d, limit=1)
            if not product and variant:
                product = variant.product_tmpl_id
            if not product:
                not_found += 1
                continue
            de = safe_str(row.get(desc_col))
            we = safe_str(row.get(web_col))
            vals = {}
            if de:
                vals["description_ecommerce"] = de
            if we:
                vals["website_description"] = we
            if vals and all(f in ProductTemplate._fields for f in vals):
                product.write(vals)
            if pricelist and variant:
                pr = safe_str(row.get(sales_col) or row.get("Sales Price") or "") if sales_col else safe_str(row.get("Sales Price") or "")
                pf = safe_float(pr)
                if pf > 0:
                    item = PricelistItem.search([("pricelist_id", "=", pricelist.id), ("applied_on", "=", "0_product_variant"), ("product_id", "=", variant.id), ("min_quantity", "=", 1)], limit=1)
                    if item:
                        item.write({"fixed_price": pf})
                    else:
                        PricelistItem.create({"pricelist_id": pricelist.id, "applied_on": "0_product_variant", "product_id": variant.id, "min_quantity": 1, "fixed_price": pf})
            updated += 1
        except Exception as e:
            _logger.warning("HTML row %s: %s", idx, e)
    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': _("HTML Import finished"), 'message': _("Updated %s products. %s rows did not match.") % (updated, not_found), 'type': 'success', 'sticky': False}}
