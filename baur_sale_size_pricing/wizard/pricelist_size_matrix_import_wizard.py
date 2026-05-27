# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from ..utils import parse_size_lower_bound

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


def _safe_float(value):
    try:
        if pd is not None and pd.isna(value):
            return 0.0
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return 0.0


def _safe_str(value):
    try:
        if pd is not None and pd.isna(value):
            return ''
    except TypeError:
        pass
    return str(value or '').strip()


def _normalize_header(value):
    return _safe_str(value).lower().replace('_', ' ')


class PricelistSizeMatrixImportWizard(models.TransientModel):
    _name = 'pricelist.size.matrix.import.wizard'
    _description = 'Import Pricelist Size Matrix'

    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True)
    xlsx_file = fields.Binary(string='XLSX File', required=True)
    xlsx_filename = fields.Char(string='Filename')

    def _read_xlsx(self, file_data):
        if pd is None:
            raise UserError(_('Please install pandas (and openpyxl) on the server to import XLSX files.'))
        try:
            decoded = base64.b64decode(file_data or b'')
        except Exception as exc:
            raise ValidationError(_('Error reading file: %s') % str(exc))
        try:
            buffer = io.BytesIO(decoded)
            workbook = pd.ExcelFile(buffer)
            sheets = [str(name).strip() for name in workbook.sheet_names]
            if not sheets:
                raise ValidationError(_('The file does not contain any worksheets.'))
            buffer.seek(0)
            return pd.read_excel(buffer, sheet_name=sheets[0], skiprows=0)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(_('Error reading XLSX workbook: %s') % str(exc))

    def _get_size_column(self, dataframe):
        for column in dataframe.columns:
            normalized = _normalize_header(column)
            if normalized in ('size', 'grosse', 'grösse', 'sqm', 'm2', 'square meter'):
                return column
        return dataframe.columns[0] if len(dataframe.columns) else None

    def _resolve_variant(self, header_label):
        Product = self.env['product.product']
        ProductTemplate = self.env['product.template']

        label = _safe_str(header_label)
        if not label:
            return self.env['product.product']

        search_labels = [label]
        if ' ' in label:
            search_labels.append(label.split()[-1])

        for search_label in search_labels:
            variant = Product.search([('default_code', '=', search_label)], limit=1)
            if variant:
                return variant

        variants = Product.search([('name', '=', label)], limit=2)
        if len(variants) == 1:
            return variants

        templates = ProductTemplate.search([('name', '=', label)], limit=2)
        if len(templates) == 1 and len(templates.product_variant_ids) == 1:
            return templates.product_variant_ids

        return self.env['product.product']

    def action_import(self):
        self.ensure_one()
        dataframe = self._read_xlsx(self.xlsx_file)
        dataframe.columns = [_safe_str(column) for column in dataframe.columns]
        size_column = self._get_size_column(dataframe)
        if not size_column:
            raise UserError(_('Could not find a size column in the XLSX file.'))

        product_columns = [column for column in dataframe.columns if column != size_column]
        if not product_columns:
            raise UserError(_('Add at least one product column next to the size column.'))

        unresolved = [column for column in product_columns if not self._resolve_variant(column)]
        if unresolved:
            raise UserError(
                _('Could not match these product columns to variants: %s') % ', '.join(unresolved)
            )

        PricelistItem = self.env['product.pricelist.item']
        created = 0
        updated = 0
        skipped = 0

        for row_index, row in dataframe.iterrows():
            size_label = _safe_str(row.get(size_column))
            if not size_label:
                continue

            lower_bound = parse_size_lower_bound(size_label)
            if lower_bound is None:
                raise UserError(_('Could not parse the size value on row %s.') % (row_index + 2))

            for product_column in product_columns:
                price = _safe_float(row.get(product_column))
                if price <= 0:
                    skipped += 1
                    continue

                variant = self._resolve_variant(product_column)
                domain = [
                    ('pricelist_id', '=', self.pricelist_id.id),
                    ('applied_on', '=', '0_product_variant'),
                    ('product_id', '=', variant.id),
                    ('min_quantity', '=', lower_bound),
                    ('date_start', '=', False),
                    ('date_end', '=', False),
                ]
                item = PricelistItem.search(domain, limit=1)
                values = {
                    'pricelist_id': self.pricelist_id.id,
                    'applied_on': '0_product_variant',
                    'product_id': variant.id,
                    'product_tmpl_id': variant.product_tmpl_id.id,
                    'min_quantity': lower_bound,
                    'compute_price': 'fixed',
                    'fixed_price': price,
                }
                if item:
                    item.write({'fixed_price': price})
                    updated += 1
                else:
                    PricelistItem.create(values)
                    created += 1

        message = _('Created: %(created)s, Updated: %(updated)s, Skipped empty prices: %(skipped)s') % {
            'created': created,
            'updated': updated,
            'skipped': skipped,
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Size matrix import'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }
