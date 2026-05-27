# -*- coding: utf-8 -*-

{
    'name': '(sd) Sale Size Pricing',
    'summary': 'Add sale lines priced from parsed size ranges',
    'description': """
Adds a sale order line popup that parses the source line size into square meters,
prices a selected add-on product from the order pricelist, and inserts the new line
after the current one. Includes a pricelist size-matrix XLSX import wizard.
""",
    'author': 'Soludoo',
    'website': 'https://www.soludoo.ch',
    'category': 'Sales',
    'version': '15.0.1.0.1',
    'license': 'OPL-1',
    'depends': [
        'base_baur',
        'sale_order_line_sequence',
        'baur_pricelist_import',
    ],
    'external_dependencies': {
        'python': ['pandas', 'openpyxl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'wizard/sale_line_size_pricing_wizard_views.xml',
        'wizard/pricelist_size_matrix_import_wizard_views.xml',
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
