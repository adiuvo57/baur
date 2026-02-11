# Sale Order Line Sequence

## Overview

The **Sale Order Line Sequence** module enhances Odoo Sales by managing and displaying a stable line sequence on sales orders and related documents. It introduces a dedicated line number field on `sale.order.line`, keeps sequence values consistent, and provides tools to insert sections or notes in between existing lines while maintaining the order. A helper field on the sale order keeps track of the maximum sequence, and a post-init hook recalculates all sequences on existing sale orders.

## Key Features

- **Stable Line Numbering**: Adds a `sequence2` field (Line Number) on sale order lines and ties the standard `sequence` field to it.
- **Automatic Sequence Reset**: Recalculates line numbering whenever sale orders are modified, ensuring a clean and consistent sequence.
- **Max Line Sequence Helper**: Maintains a computed `max_line_sequence` on `sale.order` to know the next sequence value.
- **Section and Note Insertion**: Provides a wizard to insert product, section, or note lines at specific positions while shifting subsequent lines correctly.
- **Section Link on Lines**: Allows assigning sale order lines to a section via `section_id` on `sale.order.line`.
- **Optional Sequence on Report**: Includes a QWeb extension template to show the line sequence in the sale order report.

## Installation

1. Copy the module folder **sale_order_line_sequence** into your Odoo addons directory.
2. Go to **Apps → Update Apps List**.
3. Install **Sale Order Line Sequence** from the Apps menu.

The module depends on the base **sale** module.

## Configuration

No special configuration is required.  
Once installed:

- Sale order lines will have an internal line number (`sequence2`).
- The sale order form will maintain the `max_line_sequence` helper.
- The **Add Section** and **Add Note** buttons will be available on sale orders via the add-section wizard.

If you want to use the extended sale order report with the sequence column, ensure the `report_saleorder.xml` template is active in your deployment.

## Usage

### Line Numbering on Sale Orders

On each **Sale Order**:

- A hidden field **Max sequence in lines** (`max_line_sequence`) is maintained.
- As lines are created or updated, the module ensures a consistent line numbering using `sequence2`.
- The standard `sequence` field is related to `sequence2`, so the ordering in the UI follows this custom line number.

When you edit or save the sale order, `_reset_sequence()` is called to:

- Keep sections grouped correctly.
- Maintain incremental numbering inside each section.
- Ensure there are no gaps or overlaps in the sequence.

### Adding Sections and Notes

The module introduces a transient model **Add Section** (`add.section`) used via a wizard:

1. On a sale order, the **Add Section** and **Add Note** buttons are available near the order lines.
2. Clicking **Add Section** or **Add Note** opens the **Add Section** form:

   In the wizard you can choose:
   - **Display Type** (`display_type`):
     - `product` – create a normal product line.
     - `section` – create a section header line.
     - `note` – create a note line.
   - **Product** (`product_id`) – required when display type is `product`.
   - **Section** (`section`) – text for section line when display type is `section`.
   - **Note** (`note`) – text for note line when display type is `note`.
   - **Section List** (`md_section_list`) – read-only list of existing sections in the order.
   - **Sequence** (`seq`) – target position where the new line should be inserted.

3. When you click **Add**:
   - A new sale order line is created at the chosen sequence, using:
     - `display_type = 'product'` / `'line_section'` / `'line_note'` depending on choice.
     - `sequence2` adjusted to `seq - 1`.
   - Subsequent lines are shifted and their `sequence2` values are updated.
   - `_reset_sequence()` is called to re-normalize the entire sequence of lines.

### Section Assignment on Lines

Each **sale order line** can be linked to a section:

- `section_id` – Many2one to `sale.order.line` (the line representing the section).

The view adds:

- A **Section** field next to product fields on the order line tree.
- Domain filters for `section_id` to only show section lines of the same order.

Lines under a section get sequence values computed relative to their section, helping keep a structured order layout.

### Sales Order Report (Optional)

The module includes a QWeb extension template `report_saleorder_document_sequence` (in `report_saleorder.xml`) which:

- Inserts a **Sequence** column in the sale order report table header.
- Displays `line.sequence2` for each line in the report body.

This allows printing the line number on quotations and orders.

## Security Groups

This module does **not** define new security groups.  
It uses existing Sales access rights:

- Users who can view and edit sale orders can use the add-section wizard and see the line sequence.

Model access is configured via `security/ir.model.access.csv`.

## Data Model

### Sale Order (`sale.order`)

- `max_line_sequence` – Integer (computed, stored)  
  Highest sequence value of order lines plus 1. Used as a helper for new line defaults and sequence reset.

Key methods:

- `_compute_max_line_sequence()` – Computes `max_line_sequence` from existing `order_line.sequence`.
- `_reset_sequence()` – Recalculates `sequence2` and `sequence` for all lines on the order.
- `write()` – After writing, resets sequence on the order.
- `copy()` – Copies the order with the `keep_line_sequence` context to preserve line sequences.

### Add Section Wizard (`add.section`, TransientModel)

Fields:

- `order_id` – Many2one(`sale.order`) – Target sale order.
- `product_id` – Many2one(`product.product`) – Product for product-type line.
- `display_type` – Selection(`product`, `section`, `note`) – Type of line to create.
- `hide_display_type` – Boolean – Controls visibility of display_type radio widget.
- `section` – Char – Text for section line.
- `note` – Char – Text for note line.
- `seq` – Integer – Target sequence position.
- `md_section_list` – Many2many(`sale.order.line`) – Read-only list of existing section lines in the order.

Key methods:

- `default_get()` – Loads current order sections into `md_section_list`.
- `add_line()` – Creates the appropriate line (product/section/note) at the selected sequence, adjusts subsequent lines, and triggers `_reset_sequence()`.

### Sale Order Line (`sale.order.line`)

Fields:

- `sequence` – Integer (related to `sequence2`, stored)  
  Redefined to relate to `sequence2` so UI ordering uses the custom line number.
- `sequence2` – Integer (Line Number)  
  Custom line sequence, human-friendly and used for display/print.
- `section_id` – Many2one(`sale.order.line`) – Section line this line belongs to.

Key methods:

- `create()` – After creating a line, resets the sequence on the order (unless copying with `keep_line_sequence` context).
- `action_add_section()` – Opens the Add Section wizard with context for the current line and initial `default_seq`.

## Business Logic

- **Sequence Management**  
  `_reset_sequence()` walks through the order lines, uses a base section sequence (`section_sequence`) and a running `current_sequence` to assign `sequence2`:
  - Each section line increments `section_sequence` by 1000 and sets its own sequence.
  - Non-section lines under a section get `section_id.sequence2 + current_sequence`.
  - Lines without section get `section_sequence + current_sequence`.
  - `current_sequence` increments per line, ensuring unique line numbers.

- **Post-init Hook** (`post_init_hook` in `init_hooks.py`)  
  After module installation:
  - All existing sale orders are searched.
  - `_reset_sequence()` is called on each to ensure initial sequences are consistent.

- **Copy and Keep Sequence**  
  When copying a sale order:
  - `copy()` is executed with context `keep_line_sequence=True`, so line sequences are preserved and not recomputed during copy.

## Multi-Company

The module follows standard Odoo multi-company behavior:

- Sequences are managed per order.
- No additional multi-company specific logic is added.

## Troubleshooting

### Line Numbers Look Incorrect

- Use **Edit → Save** on the sale order to force `_reset_sequence()`.
- Ensure there are no custom modules overriding `sale.order.line.sequence` behavior.

### Add Section Wizard Not Visible

- Verify the module is installed.
- Ensure the user has permission to edit sale orders.
- Check that the view inheritance from `sale.view_order_form` is correctly applied.

### Sequence Column Not Showing on Report

- Confirm the QWeb template `report_saleorder_document_sequence` is loaded and not disabled.
- Ensure your sale order report is based on `sale.report_saleorder_document`.

## Uninstallation

When the module is uninstalled:

- Custom fields (`max_line_sequence`, `sequence2`, `section_id`) remain in the database but are not used.
- Sequence behaviors revert to Odoo’s default sale order line handling.
- The Add Section wizard and related buttons are removed from the user interface.
- Optional report sequence column is removed.

## Support

**Authors**: ForgeFlow, Serpent Consulting Services Pvt. Ltd., Odoo Community Association (OCA)  
**Website**: https://github.com/OCA/sale-workflow

## License

AGPL-3 (GNU Affero General Public License v3)
