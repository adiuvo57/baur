# (sd) Swiss QR-bill – Structured Addresses (Type S)

Odoo 15 module by Soludoo. Makes the Swiss QR-bill emit **structured addresses
(address type "S")** for creditor and debtor as required by the SIX Swiss
Payment Standards (Implementation Guidelines QR-bill v2.3, binding since
21/22 November 2025), and blocks invoices whose addresses cannot be
structured.

Odoo 15 standard (`l10n_ch`) still emits the combined address type "K", which
Swiss financial institutions no longer accept. Odoo 16+ ship the structured
address natively; this module is a controlled backport plus stricter
validation.

## What it does

| Area | Behaviour |
|---|---|
| QR payload | Lines 5–10 (creditor) and 21–26 (ultimate debtor) are rewritten to `S`, name, street name, building number, postal code, town. IBAN/QR-IBAN, reference type (QRR/SCOR/NON), amount, trailer are untouched. |
| Street split | `Bahnhofstrasse 12` → `Bahnhofstrasse` / `12`. Extended for the Swiss notation `Oberdorfstrasse 20 A` (upstream Odoo does not recognise it). If the Street field has no number but Street 2 does (`c/o Firma AG` / `Auweg 41`), Street 2 is used as the postal street. |
| Character set | Names, streets, towns and the unstructured message are reduced to the SIX character set; typographic dashes/quotes are mapped, line breaks removed. |
| Validation | `_check_for_qr_code_errors` reports every missing element (country, zip, city, street, building number) with the partner name and role. |
| Posting hook | Customer invoices / credit notes whose bank account is eligible for a QR-bill are validated when posted; a `UserError` keeps the invoice in draft. Independent of the "QR codes on invoices" setting. |
| Print / send | The *Print QR-bill* button and the QR-bill report / e-mail attachment give the precise error instead of a generic one. No fallback to type K exists. |

## Settings (Accounting › Configuration › Settings › Customer Invoices, CH/LI companies)

* **QR-bill: require building number** (default on) – SIX treats street and
  number as optional; this enforces complete master data. Switch off
  temporarily if data clean-up delays go-live.
* **Validate addresses when posting customer invoices** (default on) –
  kill switch for the posting hook; printing and sending still validate.

## Data audit

```
odoo-bin shell -d <db> --no-http < scripts/audit_swiss_addresses.py
QR_AUDIT_OUT=/tmp/audit.xlsx QR_AUDIT_SCOPE=all odoo-bin shell -d <db> --no-http < scripts/audit_swiss_addresses.py
```

Writes an XLSX with one row per CH/LI partner whose address cannot be
structured (problem class, parsed street/number, link to the record).

## Tests

```
odoo-bin -d <db> -i l10n_ch_qr_structured_address --test-tags /l10n_ch_qr_structured_address --stop-after-init
```

`tests/test_street_split.py` – parser and sanitiser (no DB needed);
`tests/test_qr_payload.py` – payload, validation, posting, printing (uses the
`l10n_ch` chart of accounts).

## Acceptance (SIX)

1. Decode the QR of a test invoice (e.g. `zbarimg --raw qr.png`): lines 5 and
   21 must read `S`, followed by separate street / number / zip / town.
2. Upload the PDF to the SIX validation portal
   (https://validation.iso-payments.ch/qrrechnung): 0 errors.

## Compatibility notes

* Depends only on `l10n_ch`. Stored split fields (`street_name`,
  `street_number`) from `base_address_extended` are used automatically when
  present.
* On migration to Odoo 16+ the payload override becomes redundant (standard
  emits type S); keep the parser extension and the posting validation.
