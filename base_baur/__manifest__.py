# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
{
    'name': '(sd) Baur Report',
    'version': '1.0',
    "summary": '',
    'description': """ """,
    "category": "Sales",
    'author': 'Soludoo',
    'website': 'https://www.soludoo.ch/',
    'images': '',
    'depends': ['sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template.xml',
        'views/account_move.xml',
        'views/sale.xml',
        'report/invoice_report_views.xml',
        'report/sale_report_views.xml',
        'report/contact_report_template.xml',
    ],
    'installable': True,
}
