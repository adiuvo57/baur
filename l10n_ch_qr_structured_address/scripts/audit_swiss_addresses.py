# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
"""Audit of Swiss / Liechtenstein partner addresses for the structured QR-bill.

Lists every active partner in CH/LI whose address cannot be emitted as a
complete structured address (type S) and writes the result to an XLSX file
for correction by the customer.

Usage (Odoo shell, from the server or an Odoo.sh shell)::

    odoo-bin shell -d <database> --no-http < scripts/audit_swiss_addresses.py

    # options via environment variables
    QR_AUDIT_OUT=/tmp/qr_address_audit.xlsx   output file (default shown)
    QR_AUDIT_SCOPE=customers                  customers (default) | all

On Odoo.sh the file lands in the build's filesystem; download it with the
Odoo.sh shell (``cat`` / ``base64``) or run the script against a local copy.

Problem classes reported
------------------------
missing country, missing zip, missing city, no street, no building number,
building number > 16, street > 70, city > 35, unparseable characters removed.
"""
import os

from odoo.addons.l10n_ch_qr_structured_address.tools.address import (  # noqa: E402
    MAX_BUILDING_NUMBER, MAX_STREET, MAX_TOWN, sanitize_text, street_split, structured_address,
)

OUT = os.environ.get('QR_AUDIT_OUT', '/tmp/qr_address_audit.xlsx')
SCOPE = os.environ.get('QR_AUDIT_SCOPE', 'customers')

env = env  # noqa: F821 - provided by odoo shell
Partner = env['res.partner'].with_context(active_test=True)

domain = [('country_id.code', 'in', ('CH', 'LI'))]
if SCOPE == 'customers':
    domain.append(('customer_rank', '>', 0))
partners = Partner.search(domain, order='display_name')

# customers without country at all: they silently get no QR-bill
no_country = Partner.search([('country_id', '=', False), ('customer_rank', '>', 0)]) if SCOPE == 'customers' else Partner.browse()

rows = []


def problems_for(partner):
    problems = []
    if not partner.country_id:
        problems.append('missing country')
    if not partner.zip:
        problems.append('missing zip')
    if not partner.city:
        problems.append('missing city')
    addr = structured_address(partner.street, partner.street2, partner.zip, partner.city)
    if not addr['street']:
        problems.append('no street')
    elif not addr['number']:
        problems.append('no building number')
    if len(sanitize_text(partner.street)) > MAX_STREET:
        problems.append('street > %d' % MAX_STREET)
    raw_number = street_split(sanitize_text(partner.street))['street_number'] or street_split(sanitize_text(partner.street2))['street_number']
    if len(raw_number) > MAX_BUILDING_NUMBER:
        problems.append('building number > %d (truncated)' % MAX_BUILDING_NUMBER)
    if len(sanitize_text(partner.city)) > MAX_TOWN:
        problems.append('city > %d (truncated)' % MAX_TOWN)
    for field in ('name', 'street', 'street2', 'city'):
        value = partner[field] or ''
        if value and sanitize_text(value) != ' '.join(value.split()):
            problems.append('forbidden characters in %s' % field)
            break
    return problems, addr


for partner in partners:
    problems, addr = problems_for(partner)
    if problems:
        rows.append((
            partner.id, partner.display_name, partner.street or '', partner.street2 or '',
            partner.zip or '', partner.city or '', partner.country_id.code or '',
            addr['street'], addr['number'], addr['source'], ', '.join(problems),
            '/web#id=%d&model=res.partner&view_type=form' % partner.id,
        ))

for partner in no_country:
    rows.append((
        partner.id, partner.display_name, partner.street or '', partner.street2 or '',
        partner.zip or '', partner.city or '', '', '', '', '', 'missing country (no QR-bill at all)',
        '/web#id=%d&model=res.partner&view_type=form' % partner.id,
    ))

try:
    import xlsxwriter  # shipped with Odoo
except ImportError:  # pragma: no cover
    xlsxwriter = None

if xlsxwriter:
    workbook = xlsxwriter.Workbook(OUT)
    sheet = workbook.add_worksheet('QR address audit')
    bold = workbook.add_format({'bold': True, 'bg_color': '#1D1E20', 'font_color': '#FFFFFF'})
    headers = ['ID', 'Partner', 'Street', 'Street 2', 'ZIP', 'City', 'Country',
               'Parsed street', 'Parsed number', 'Rule', 'Problems', 'Link']
    for col, header in enumerate(headers):
        sheet.write(0, col, header, bold)
    for row_index, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            sheet.write(row_index, col, value)
    sheet.autofilter(0, 0, max(len(rows), 1), len(headers) - 1)
    sheet.freeze_panes(1, 0)
    sheet.set_column(1, 1, 32)
    sheet.set_column(2, 3, 28)
    sheet.set_column(7, 7, 24)
    sheet.set_column(10, 10, 48)
    workbook.close()
    print('%d partners with problems (of %d scanned) → %s' % (len(rows), len(partners), OUT))
else:
    print('%d partners with problems (of %d scanned); xlsxwriter missing, printing CSV' % (len(rows), len(partners)))
    for row in rows:
        print(';'.join(str(v) for v in row))
