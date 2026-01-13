# -*- coding: utf-8 -*-
{
    'name' : 'Scan your QR-Factures (QR-invoices) easily',
    'version' : '1.0',
    'author' : 'nivels GmbH',
    'category' : 'Accounting',
    'website': 'https://www.nivels.ch',
    'license': 'AGPL-3',
    'description' : """
**Features list :**
    * Allows you to scan swiss QR code from swiss invoice (paper) and autofill informations in account invoice (odoo).
""",
    'depends' : [
        'l10n_ch'
    ],
    'data': [
        'wizard/qr_code_scan_to_invoice.xml',
        'views/view_res_partner.xml',
        'views/view_res_company.xml',
        'views/sale.xml',
        'security/ir.model.access.csv',

    ],
    'installable': True,
    'auto_install': True,
    'images': [
        'static/description/QR_ready.png'
    ]
}
