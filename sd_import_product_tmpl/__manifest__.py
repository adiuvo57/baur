# -*- coding: utf-8 -*-


{
    'name': '(sd) Import Product Template',
    'summary': """The "Import Product Template" module is a versatile and indispensable tool designed to simplify and streamline the process of importing product data into your system. It provides a user-friendly interface and a range of features that empower users to efficiently and accurately populate their product databases.
    Product Import | Import Product Template | Product Template | Product | Data Integration | Data Mapping | CSV Import | Excel Import | Data Validation | Bulk Import | Error Handling | Security | Reporting | Data Management | User-Friendly Interface | System Integration | Data Integrity
    """,
    'description': """The "Import Product Template" module serves as a pivotal component within your data management ecosystem, facilitating the seamless integration of external product data sources with your system.
    """,
    "author": "Soludoo",
    "website": "https://www.soludoo.ch",
    'category': 'Extra Tools',
    'version': '19.0.1.0',
    'license': 'OPL-1',
    'depends': ['sale_management', 'product', 'website_sale'],
    'data': [
            'security/ir.model.access.csv',
            "wizard/import_product_tmpl_wizard.xml",
            "views/product_view.xml",
             ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    'price': 12,
    'currency': "USD",
}
