# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
{
    'name': '(sd) Baur Provision',
    # Bumped for Odoo 19.0 while keeping the same functional behavior as 15.0
    'version': '19.0.1.0.0',
    "summary": '',
    'description': """ """,
    "category": "Sales",
    'license': 'OPL-1',
    'author': 'Soludoo',
    'website': 'https://www.soludoo.ch',
    'images': '',
    'depends': ['sale_management', 'account'],
    'data': [
        'views/sale.xml',
        'report/sale_report_views.xml',
    ],
    'installable': True,
}
