# -*- coding: utf-8 -*-


{
    'name': '(sd) Pricelist XLSX Import',
    'summary': 'Import pricelist rules from XLSX (product name, variant reference, qty, fixed price)',
    'description': """Bulk import fixed-price pricelist lines from Excel: optional product name check,
    variant internal reference, minimum quantity, and price. Includes sample XLSX.
    """,
    "author": "Soludoo",
    "website": "https://www.soludoo.ch",
    'category': 'Extra Tools',
    'version': '15.0.1.0.0',
    'license': 'OPL-1',
    'depends': ['product'],
    'external_dependencies': {
        'python': ['pandas', 'openpyxl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'wizard/pricelist_import_wizard_views.xml',
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
