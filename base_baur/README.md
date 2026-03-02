# (sd) Baur Report

## Overview
The **(sd) Baur Report** module extends Odoo Sales, Products, Accounting, and Invoicing functionality with additional custom fields and report enhancements specifically used for Baur-format quotations, invoices, and sales reports. The module introduces new product attribute fields, additional sale order metadata, improved invoice and sale report templates, and extended partner and user fields to support printing formats and layout requirements.

## Key Features
- **Custom Product Fields**: Adds color (`farbe`) and size (`grosse`) attributes to product templates.
- **Extended Sale Order Fields**: Adds several fields used for printed quotation and report customization, including warranty text, custom free text blocks, boolean flags for work services, and formatting options.
- **Baur-Format Reporting**: Custom sale and invoice report templates included in `report_templates.xml`, `invoice_report_views.xml`, and `sale_report_views.xml`.
- **Customer & User Extensions**: Adds additional informational fields to `res.partner` and `res.users` for reporting purposes.
- **Studio-Compatible Fields**: Supports fields for imported Studio data (x_studio fields).
- **Report Layout Enhancements**: Enables custom blocks and formatting for printed document design in Sales and Accounting.

## Installation
1. Copy the module into your Odoo addons directory.
2. Go to **Apps → Update Apps List**.
3. Install **(sd) Baur Report** from the Apps menu.

## Configuration
No special configuration is required.  
After installation, new fields become available in product templates, sale orders, partner forms, and user profiles. Reports will automatically use the enhanced formats on quotations and invoices.

## Usage

### Product Enhancements
Open **Products → Products** and edit a product:
- **Farbe**: Color selection using model `x_farben` (Many2one field)
- **Grosse**: Size description (Char field)

These product values appear automatically in Sales and Report templates.

### Sales Order Enhancements
Open a Sale Order and configure:
- **Garantie Wiederverkäufer** fields and text blocks
- **Freier Text Block** and **Freier Text (HTML)**
- Service option flags:
  - Ausmessen, liefern und montieren
  - Reparieren / Ersetzen von
- Report formatting assistance fields
- Custom Pricelist behavior: changing pricelist affects only new lines

Changes affect printed quotation and invoice outputs.

### Reporting
Enhanced Baur-formatted print-outs:
- **Sales Report** templates
- **Invoice Report** templates

Accessible from standard:
- **Print → Quotation / Order**
- **Print → Invoice**

### Partner & User Information
Additional informational fields are displayed in forms:
- **Partner**: `x_studio_name2` – second person name field
- **User**: `x_studio_initialen` – initials for report signature formatting

## Security Groups
This module **does not** introduce any new security groups.  
Standard Sales and Accounting permissions apply for editing data and printing reports.

## Data Model

### Product Template Fields
| Field | Type | Description |
|-------|-------|------------|
| `farbe` | Many2one(`x_farben`) | Product color |
| `grosse` | Char | Product size |

### Sale Order Fields (from `sale.py`)
| Field | Type | Description |
|--------|--------|-------------|
| `garantie_wiederverkaufer_sep` | Char | Warranty separator title |
| `garantie_wiederverkaufer_label` | Char | Warranty label |
| `garantie_wiederverkaufer_text` | Text | Warranty text body |
| `freier_text_block_id` | Many2one(`text.blocks`) | Free text block selector |
| `freier_text` | Html | Custom formatted free text |
| `ausmessen_liefern_und_montieren` | Boolean | Work service option |
| `ausmessen_liefern_und_montieren_text` | Char | Service label |
| `reparieren_ersetzen_von` | Boolean | Repair/replace option |
| `reparieren_ersetzen_von_text` | Char | Repair/replace label |
| `remove_order_existing_line` | Boolean | Remove existing lines |
| `pricelist_id` | Many2one(`product.pricelist`) | Affects only newly added lines |

Additional studio fields:
| Field | Type | Description |
|--------|--------|-------------|
| `x_studio_groesse` | Char | Size |
| `x_studio_farbe` | Many2one(`x_farben`) | Color |

### Partner Fields
| Field | Type | Description |
|--------|-------|-------------|
| `x_studio_name2` | Char | Second name line |

### User Fields
| Field | Type | Description |
|--------|-------|-------------|
| `x_studio_initialen` | Char | Initials |

## Business Logic
- Onchange behavior updates free text content based on selected text block (`onchange_freier_text_block_id`)
- Pricelist updates affect only newly added lines, preserving existing pricing logic

## Multi-Company
Standard Odoo behavior.  
No module-specific multi-company logic applied.

## Troubleshooting
### Report output does not show new fields
- Ensure correct print template selection
- Verify fields filled on product & sale order

### Fields missing on UI
- Check if Studio or user access rights hide custom fields

## Developer Notes
- Reports implemented in:  
  `report_templates.xml`, `invoice_report_views.xml`, `sale_report_views.xml`
- Views extended in:  
  `product_template.xml`, `sale.xml`, `account_move.xml`

## Uninstallation
- Can be safely uninstalled
- Custom fields remain in DB but unused
- Report templates revert to default Odoo formats

## Support
**Author**: Soludoo  
**Website**: https://www.soludoo.ch/

## License
OPL-1 (Odoo Proprietary License v1.0)
