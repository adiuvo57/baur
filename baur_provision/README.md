# (sd) Baur Provision

## Overview

The **(sd) Baur Provision** module extends Odoo Sales and Accounting to track the introducing partner (“vermittelt durch”) on sales orders, invoices, and analysis reports. It adds a single relational field to sales orders and propagates this value to customer invoices, invoice reporting, and sales reporting. The field is also available in search filters, making it easy to analyze turnover and invoices by the originating partner.

## Key Features

- **Vermittelt Durch on Sales Orders**: Adds a `(sd) vermittelt durch` partner field to the sale order.
- **Propagation to Invoices**: Automatically copies the `vermittelt_durch_id` from the sale order to generated invoices.
- **Advance Invoices Support**: Ensures the field is set on invoices created via the down payment (advance payment) wizard.
- **Invoice Form & Search Filters**: Shows the `(sd) vermittelt durch` field on invoices and adds a dedicated filter.
- **Sales & Invoice Reporting**: Extends `sale.report` and `account.invoice.report` with the `vermittelt_durch_id` field for grouping and filtering.
- **Minimal & Focused**: No configuration, no extra security groups, just the additional field and reporting integration.

## Installation

1. Copy the module into your Odoo addons directory.
2. Go to **Apps → Update Apps List**.
3. Install **(sd) Baur Provision** from the Apps menu.

## Configuration

No special configuration is required.  
After installation:

- The `(sd) vermittelt durch` field is visible on the sale order form.
- The same field appears on invoices.
- New filters and fields are available in Sales Analysis and Invoice Analysis views.

## Usage

### Sales Orders

1. Open **Sales → Orders → Quotations / Orders**.
2. On the sale order form, set the **(sd) vermittelt durch** field (`vermittelt_durch_id`) with the appropriate partner (res.partner).
3. Confirm the sale order as usual.

When invoices are created from the sale order (standard invoice or grouped invoice), the same `vermittelt_durch_id` value is copied to the invoice.

### Customer Invoices

- The **(sd) vermittelt durch** field is available on **account.move** (customer invoice/credit note).
- The module ensures this field is filled automatically when:
  - Creating invoices from sale orders (`_create_invoices` override).
  - Creating down payments / advance invoices via **Create Invoice** wizard (`sale.advance.payment.inv`).

You can also filter invoices that have a Vermittler (introducing partner) using the dedicated search filter.

### Sales & Invoice Reports

The module extends:

- **Sales Analysis** (`sale.report`):
  - Adds field **vermittelt_durch_id**.
  - Makes it available in the search view with a filter for non-empty values.
  - Extends group-by logic to include `s.vermittelt_durch_id`.

- **Invoice Analysis** (`account.invoice.report`):
  - Adds field **vermittelt_durch_id**.
  - Includes it in the main SELECT query from `account.move`.
  - Adds it to the search view with a filter for `vermittelt_durch_id` not empty.

You can now group or filter sales and invoice analysis by the introducing partner.

## Security Groups

This module **does not** introduce any new security groups.  
Access is controlled by existing Sales and Accounting permissions.

Users who can see sale orders, invoices, and analysis reports will see the `(sd) vermittelt durch` field accordingly.

## Data Model

### Sale Order (`sale.order`)

- `vermittelt_durch_id` – Many2one(`res.partner`) – **(sd) vermittelt durch** on the sale order.

### Account Move (`account.move`)

- `vermittelt_durch_id` – Many2one(`res.partner`) – **(sd) vermittelt durch** on invoices and credit notes.

### Sale Report (`sale.report`)

- `vermittelt_durch_id` – Many2one(`res.partner`) – Read-only field included in the sales analysis.

The module:
- Extends `_group_by_sale()` to group by `s.vermittelt_durch_id`.
- Extends `_select_additional_fields()` to select `s.vermittelt_durch_id` as `vermittelt_durch_id`.

### Account Invoice Report (`account.invoice.report`)

- `vermittelt_durch_id` – Many2one(`res.partner`) – Read-only field included in the invoice analysis.

The module:
- Extends `_select()` to add `move.vermittelt_durch_id as vermittelt_durch_id` to the invoice report select clause.

## Business Logic

- **Invoice Creation from Sale Orders**  
  The overridden `_create_invoices` method on `sale.order` sets:
  - `invoice.vermittelt_durch_id = sale_order.vermittelt_durch_id` (or `None` if empty).

- **Advance Payment / Down Payment Invoices**  
  The `_prepare_invoice_values` method on `sale.advance.payment.inv` is extended to:
  - Add `vermittelt_durch_id` to the invoice values dict from `order.vermittelt_durch_id`.

- **Reporting**  
  - `sale.report`’s group-by and select are updated to include `s.vermittelt_durch_id`.
  - `account.invoice.report`’s select is extended to include `move.vermittelt_durch_id`.

## Multi-Company

The module follows standard Odoo multi-company behavior.  
The `vermittelt_durch_id` field is company-agnostic and behaves like any other Many2one(`res.partner`) field across companies.

## User Interface & Views

### Views

- `views/sale.xml`:
  - Extends the **sale order form** to show `vermittelt_durch_id` (before `currency_id`).
  - Extends the **account.move (invoice) form** to display `vermittelt_durch_id`.
  - Extends the **account.move search/filter view** to add:
    - A separator.
    - A filter named `vermittelt_durch` with domain `[('vermittelt_durch_id','!=', False)]`.

- `report/sale_report_views.xml`:
  - Extends **sale.report** search view to add `vermittelt_durch_id` field and filter.
  - Extends **account.invoice.report** search view to add `vermittelt_durch_id` field and filter.

## Troubleshooting

### Vermittelt Durch not appearing on invoices

- Ensure the field is set on the originating sale order.
- Confirm invoices are created from the sale order (not manually).
- Check that the module is correctly installed and not overridden by other custom modules.

### Filters not visible in reports

- Confirm you are using:
  - **Sales → Reporting → Sales** for `sale.report`
  - **Invoicing / Accounting → Reporting → Invoices** for `account.invoice.report`
- Make sure your user has rights to those menus.

## Uninstallation

The module can be safely uninstalled:

- Fields `vermittelt_durch_id` on related models will remain in the database but will no longer be used.
- Search filters and reporting extensions provided by this module will be removed.
- Standard Odoo behavior for reports and invoice creation is restored.

## Support

**Author**: Soludoo  
**Website**: https://www.soludoo.ch

## License

OPL-1 (Odoo Proprietary License v1.0)
