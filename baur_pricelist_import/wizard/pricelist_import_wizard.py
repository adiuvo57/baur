# -*- coding: utf-8 -*-
import base64
import io
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError

from .pricelist_import_helpers import detect_columns, safe_float, safe_str

_logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


class PricelistImportWizard(models.TransientModel):
    _name = 'pricelist.import.wizard'
    _description = 'Import Pricelist from XLSX'

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        required=True,
        readonly=True,
    )
    xlsx_file = fields.Binary(string='XLSX File', required=True)
    xlsx_filename = fields.Char(string='Filename')

    def _read_xlsx(self, file_data):
        if pd is None:
            raise UserError(_('Please install pandas (and openpyxl) on the server to import XLSX files.'))
        try:
            decoded = base64.b64decode(file_data or b'')
        except Exception as e:
            raise ValidationError(_('Error reading file: %s') % str(e))
        try:
            buf = io.BytesIO(decoded)
            xls = pd.ExcelFile(buf)
            sheets = [str(s).strip() for s in xls.sheet_names]
            if not sheets:
                raise ValidationError(_('The file does not contain any worksheets.'))
            buf.seek(0)
            return pd.read_excel(buf, sheet_name=sheets[0], skiprows=0)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_('Error reading XLSX workbook: %s') % str(e))

    def action_import(self):
        self.ensure_one()
        if not self.pricelist_id:
            raise UserError(_('No pricelist selected.'))
        df = self._read_xlsx(self.xlsx_file)
        df.columns = [str(c).strip() for c in df.columns]
        name_col, ref_col, qty_col, price_col = detect_columns(df)
        if not ref_col:
            raise UserError(
                _('Could not find a variant reference column. '
                  'Use a header such as "Variant Internal Reference" or "Internal Reference".')
            )
        if not qty_col:
            raise UserError(_('Could not find a quantity column. Use "Qty" or "Min Quantity".'))
        if not price_col:
            raise UserError(_('Could not find a price column. Use "Price" or "Fixed Price".'))

        Product = self.env['product.product']
        Item = self.env['product.pricelist.item']

        created = updated = 0
        skipped = []
        errors = []

        for idx, row in df.iterrows():
            ref = safe_str(row.get(ref_col))
            if not ref:
                continue
            qty = safe_float(row.get(qty_col))
            price = safe_float(row.get(price_col))
            if qty < 0:
                errors.append(_('Row %(r)s: negative quantity for %(ref)s') % {'r': idx + 2, 'ref': ref})
                continue
            if price <= 0:
                errors.append(_('Row %(r)s: price must be positive for %(ref)s') % {'r': idx + 2, 'ref': ref})
                continue

            variant = Product.search([('default_code', '=', ref)], limit=1)
            if not variant:
                skipped.append(_('Row %(r)s: no variant with internal reference "%(ref)s"') % {'r': idx + 2, 'ref': ref})
                continue

            if name_col:
                pname = safe_str(row.get(name_col))
                if pname and not self._variant_matches_product_name(pname, variant):
                    errors.append(
                        _('Row %(r)s: product name "%(n)s" does not match variant %(ref)s') % {
                            'r': idx + 2,
                            'n': pname,
                            'ref': ref,
                        }
                    )
                    continue

            domain = [
                ('pricelist_id', '=', self.pricelist_id.id),
                ('applied_on', '=', '0_product_variant'),
                ('product_id', '=', variant.id),
                ('min_quantity', '=', qty),
            ]
            item = Item.search(domain, limit=1)
            vals = {
                'pricelist_id': self.pricelist_id.id,
                'applied_on': '0_product_variant',
                'product_id': variant.id,
                'product_tmpl_id': variant.product_tmpl_id.id,
                'min_quantity': qty,
                'compute_price': 'fixed',
                'fixed_price': price,
            }
            if item:
                item.write({'fixed_price': price})
                updated += 1
            else:
                Item.create(vals)
                created += 1

        parts = [_('Created: %s') % created, _('Updated: %s') % updated]
        if skipped:
            parts.append(_('Skipped (not found): %s') % len(skipped))
            for s in skipped[:15]:
                parts.append(s)
            if len(skipped) > 15:
                parts.append(_('… and %s more') % (len(skipped) - 15))
        if errors:
            parts.append(_('Errors: %s') % len(errors))
            for e in errors[:15]:
                parts.append(e)
            if len(errors) > 15:
                parts.append(_('… and %s more') % (len(errors) - 15))

        msg = '\n'.join(parts)
        if errors:
            raise UserError(msg)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Pricelist import'),
                'message': msg,
                'type': 'success' if not skipped else 'warning',
                'sticky': bool(skipped),
            },
        }

    def _variant_matches_product_name(self, sheet_name, variant):
        """If the sheet has a product name, it must match the Odoo product (template or variant)."""
        a = sheet_name.strip().lower()
        tmpl = (variant.product_tmpl_id.name or '').strip().lower()
        tmpl = ' '.join(tmpl.split())
        a = ' '.join(a.split())
        if tmpl and (a == tmpl or a in tmpl or tmpl in a):
            return True
        vname = (variant.name or '').strip().lower()
        vname = ' '.join(vname.split())
        if vname and (a == vname or a in vname or vname in a):
            return True
        disp = (variant.display_name or '').strip().lower()
        disp = ' '.join(disp.split())
        if disp and (a == disp or a in disp or disp in a):
            return True
        return False
