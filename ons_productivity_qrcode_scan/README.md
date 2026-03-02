# QRCODE_SCAN (Switzerland only)

Le but de ce module est de permettre la génération de facture dans Odoo à partir d'un QR code (uniquement en Suisse et au Liechtenstein).

Il est conçu pour fonctionner avec un QR code scan [comme celui-ci par exemple.](https://www.zebra.com/fr/fr/products/scanners/general-purpose-scanners/handheld/ds2200-series.html)

## Vérification
Le compte fourni par le QR code doit être au format IBAN.
Si le débiteur précisé par le QR code n'existe pas, il sera créer en tant que contact avec l'adrese fournie.
Attention, si le débiteur n'existe pas mais que l'IBAN précisé par le QR code existe, le système va lever une erreur d'utilisation.


## Comment utiliser la fonction "QR code scan" ?
Dans le module "accounting", cliquez sur Achats dans le menu puis QR code.
Un wizard s'ouvre : vous pouvez scanner votre QR code.
Un fois le QR code scanné, vous cliquez sur le bouton "Générer facture".
La facture est alors générée à l'état "brouillon", vous n'avez plus qu'à la comptabiliser et/ou enregistrer un paiement.

##### Scan your QR-Factures (QR-invoices) easily

## Overview

The **ons_productivity_qrcode_scan** module allows you to scan Swiss QR codes (QR-factures / QR-invoices) from paper invoices and automatically generate a draft vendor bill in Odoo. It parses the content of the Swiss QR code, creates or reuses the supplier and bank account (IBAN), and prepares an `account.move` (vendor invoice) with the correct partner, bank, payment reference, amount and a single invoice line using configurable QR product and tax. 

In addition, the module adds a small sales extension field (`execution`) on sale orders and makes it available in the Sales Analysis report.

## Key Features

- **Swiss QR Invoice Scan Wizard**: Wizard (`qrcode.scan`) to paste or scan the Swiss QR code payload and generate a draft vendor bill.
- **Automatic Supplier Creation/Reuse**: Locates an existing supplier based on name and address, or creates a new one from QR data.
- **IBAN & Bank Account Management**: Reuses an existing IBAN if it belongs to the supplier, or creates a new `res.partner.bank` record; blocks duplicated IBAN conflicts.
- **Vendor Bill Generation**: Creates a vendor bill (`account.move` with `move_type = in_invoice`) from QR data, including payment reference and invoice line.
- **Configurable QR Product & Tax**: Configuration on both **Company** and **Partner** to define default product and tax used on generated invoice lines.
- **Execution Field on Sales Orders**: Adds a free-text field `execution` on `sale.order` and exposes it in `sale.report` for analysis.

## Installation

1. Copy the module directory **ons_productivity_qrcode_scan** into your Odoo addons path.
2. Update the apps list (**Apps → Update Apps List**).
3. Install **Scan your QR-Factures (QR-invoices) easily**.
4. Ensure the Swiss localization (**l10n_ch**) is installed, as this module depends on it.

> The module is flagged as `auto_install = True`, so it will install automatically when the Swiss localization is present.

## Configuration

### Company Configuration

Go to **Settings → Companies → (Your Company)**, then:

- Under the **QR code** section (in the company form):
  - **QR Product** (`qr_product_id`): Product to use for QR-generated invoice lines if no supplier-specific product is defined.
  - **QR Tax** (`qr_account_tax_id`): Tax to apply on QR-generated invoice lines if no supplier-specific tax is defined.

### Partner Configuration

Go to **Contacts → Customers / Vendors → (Supplier)**, then:

- Under the **QR code** section (on the Accounting tab):
  - **QR Product** (`qr_product_id`): Product used for QR invoices of this supplier (overrides company product).
  - **QR Tax** (`qr_account_tax_id`): Tax used for QR invoices of this supplier (overrides company tax).

## Usage

### Preparing to Scan

1. Make sure your **company** has a default QR Product and QR Tax configured (and optionally, each supplier has its specific ones).
2. Ensure you have the **Swiss QR invoice** with a valid QR code and that your scanner or copy/paste can provide the raw QR payload (multi-line text).

### Running the QR Scan Wizard

The module provides a wizard model `qrcode.scan` with a form view titled **Post QR Code infos**:

1. Open the **Scan QR Code** action (window action defined on `qrcode.scan`).
2. In the wizard:
   - Paste or scan the QR payload into **Valeur du QR** (`qrcode_value`).
3. Click **Générer la facture** (Generate the invoice).

The wizard will:

- Split the QR content into lines (`qrcode_value.split('\n')`).
- Extract supplier IBAN, address type, name, street, ZIP, and city from the QR data.
- Set the generated vendor bill as **in_invoice** (`move_type = 'in_invoice'`).
- Look for an existing supplier (`res.partner`) matching name, ZIP, and city:
  - If found, use it.
  - Otherwise, create a new supplier from QR data.
- Look for an existing bank account (`res.partner.bank`) with the same IBAN:
  - If the IBAN exists for another partner, it raises an error to avoid conflicts.
  - If not found, creates a new bank account linked to the supplier.
- Set **Payment Reference** on the invoice from QR data (`payment_reference` from the appropriate line).
- Choose a product for the invoice line:
  - Supplier’s **QR Product** (`supplier.qr_product_id`) if defined;
  - Else company’s **QR Product** (`company.qr_product_id`);
  - If neither exists, raises an error asking to configure the QR product.
- Choose a tax for the invoice line:
  - Supplier’s **QR Tax** (`supplier.qr_account_tax_id`) if defined;
  - Else company’s **QR Tax** (`company.qr_account_tax_id`);
  - If neither exists, raises an error asking to configure the QR tax.
- Build one invoice line with:
  - `product_id` set to the chosen product;
  - `tax_ids` set to the chosen tax;
  - `price_unit` derived from the QR code amount entry.
- Create the vendor bill (`account.move`) with partner, bank, payment reference and invoice line.
- Open the created invoice in **form view** in draft state for review.

### Sales Order Execution Field

On the Sales Order:

- The module adds an **Execution** (`execution`) Char field to `sale.order`.
- It is inserted before `currency_id` on the sales order form.
- A read-only **Execution** field is also added to `sale.report` so you can:
  - Analyze Sales by this free-text execution information.
  - Use it in group-by and search (via `sale_report.py` extending `_group_by_sale` and `_select_additional_fields`).

## Security Groups

The module uses standard Odoo security mechanisms:

- **Wizard `qrcode.scan`** is accessible to users who have rights to create vendor bills and use wizards in Accounting.
- No new custom security groups are defined.
- Access rights are configured through `security/ir.model.access.csv`.

## Data Model

### Company (`res.company`)

- `qr_product_id` – Many2one(`product.product`) – Default product for QR-generated invoice lines.
- `qr_account_tax_id` – Many2one(`account.tax`) – Default tax for QR-generated invoice lines.

### Partner (`res.partner`)

- `qr_product_id` – Many2one(`product.product`) – Supplier-specific product for QR-generated invoices.
- `qr_account_tax_id` – Many2one(`account.tax`) – Supplier-specific tax for QR-generated invoices.

### Sales Order (`sale.order`)

- `execution` – Char – Execution description / note shown on the sale order and used in reporting.

### Sales Report (`sale.report`)

- `execution` – Char (readonly) – Execution text included in sales analysis; added to `_group_by_sale` and `_select_additional_fields` for grouping and selection.

### QR Scan Wizard (`qrcode.scan`)

- `qrcode_value` – Text – Raw QR payload content (multi-line text) to be parsed into an invoice.

## Business Logic

- **QR Parsing**  
  The wizard splits the scanned QR content into lines and interprets specific indices as IBAN, address type, name, address details, amount, and payment reference.

- **Supplier Resolution**  
  Searches for an existing `res.partner` using:
  - name (ilike),
  - ZIP,
  - city.

  If none is found, a new supplier partner is created.

- **IBAN & Bank Validation**  
  Ensures:
  - If an IBAN already exists in `res.partner.bank` for another partner, raise a `UserError`.
  - Otherwise creates or reuses the bank account and links it to the invoice via `partner_bank_id`.

- **Invoice Creation**  
  - Sets `move_type = 'in_invoice'`.
  - Fills `partner_id`, `partner_bank_id`, `payment_reference`.
  - Creates a single invoice line using configured QR product and tax.
  - Opens the resulting invoice in a form view.

- **Sales Reporting**  
  - In `sale.report`, `execution` is added to the grouping and select logic so it can be used in analysis.

## Multi-Company

- The module respects Odoo’s standard multi-company rules.
- Company defaults (`qr_product_id`, `qr_account_tax_id`) are company-specific.
- Suppliers and bank accounts are also company-aware as per core Odoo behavior.

## Troubleshooting

### Error: “Please define QR product on company (account tab)”

- Set **QR Product** either on:
  - The supplier (Contact form → QR code section), or
  - The company (Company form → QR code section).

### Error: “Please define QR tax on company (account tab)”

- Set **QR Tax** on:
  - The supplier, or
  - The company, similar to product.

### Error around IBAN (IBAN already exists)

- Indicates the same IBAN is already used by another partner.
- Review your supplier data to ensure the correct partner is used and avoid IBAN duplication.

### Invoice not generated

- Check that:
  - The QR content is valid and complete.
  - Required company/supplier QR product & tax are configured.
  - User has permission to create vendor bills.

## Uninstallation

The module can be safely uninstalled:

- QR-related fields (`qr_product_id`, `qr_account_tax_id`, `execution`) remain in the database but are no longer used.
- The wizard and related views/actions are removed.
- Sales reporting returns to its default behavior without the `execution` field.

## Support

**Author**: nivels GmbH  
**Website**: https://www.nivels.ch

## License

AGPL-3 (GNU Affero General Public License v3)
