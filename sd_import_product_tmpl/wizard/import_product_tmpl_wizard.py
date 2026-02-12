# -*- coding: utf-8 -*-
import base64
import io
import logging

import pandas as pd

from odoo import fields, models, _
from odoo.exceptions import ValidationError

from .import_logic import ImportLogic

_logger = logging.getLogger(__name__)


class ImportProductWizard(models.TransientModel):
    _name = 'import.product.wizard'
    _description = 'Import Product Wizard'

    xlsx_file = fields.Binary(string='XLSX File', required=True)
    import_mode = fields.Selection(
        [
            ("standard", "Standard Product Import"),
            ("html_only", "Update HTML Descriptions Only"),
        ],
        string="Import Mode",
        default="standard",
        required=True,
        help="Full product import or only update HTML description fields on existing products.",
    )

    def import_xlsx_file(self):
        if self.import_mode == "html_only":
            return ImportLogic(self.env).run_html_only(self.xlsx_file)
        df = self._read_xlsx_to_df(self.xlsx_file)
        return ImportLogic(self.env).run_standard(df, self._name, self.id)

    def _read_xlsx_to_df(self, file_data):
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
            return pd.read_excel(buf, sheet_name=sheets[0], skiprows=0)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(_("Error reading XLSX workbook: %s") % str(e))
