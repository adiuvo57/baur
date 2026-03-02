# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
{
    'name': '(sd) Baur Report',
    # Bumped for Odoo 19.0 while keeping the same functional behavior as 15.0
    'version': '19.0.1.0.0',
    "summary": 'Baur custom reports and fields',
    'description': '',
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
