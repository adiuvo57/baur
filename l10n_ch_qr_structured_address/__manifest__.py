# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
{
    'name': '(sd) Swiss QR-bill – Structured Addresses (Type S)',
    'version': '15.0.1.0.0',
    'summary': 'Emit SIX IG 2.3 structured addresses (type S) in Swiss QR-bills and '
               'block invoices whose addresses cannot be structured',
    'description': """
Swiss QR-bill – Structured Addresses (Type S)
=============================================

Since 22 November 2025 the Swiss Payment Standards (SIX Implementation
Guidelines QR-bill v2.3) no longer permit the *combined* address type "K"
in newly created QR-bills.  Odoo 15 still emits type "K" for the creditor
and the debtor.  This module

* rewrites the creditor and ultimate-debtor blocks of the Swiss QR payload
  to address type "S" (street name, building number, postal code, town and
  country in separate elements),
* splits street and building number with a parser backported from Odoo 16+
  and extended for the Swiss "Bahnhofstrasse 20 A" notation,
* sanitises every free-text element to the SIX character set,
* validates creditor and debtor addresses when a customer invoice is
  posted, printed or sent, with an explicit error message instead of a
  silently broken QR code,
* ships an audit script that lists partners whose address cannot be
  structured.
""",
    'category': 'Accounting/Localizations',
    'author': 'Soludoo',
    'website': 'https://www.soludoo.ch/',
    'license': 'OPL-1',
    'depends': ['l10n_ch'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
