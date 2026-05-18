# -*- coding: utf-8 -*-
{
    'name': 'SOLe Kenya — Market Localisation',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Kenya-specific adaptations: KRA PIN, counties, 16% VAT, M-Pesa invoice widgets, KES currency',
    'description': """
SOLe Kenya Localisation
========================
Kenyan market adaptations built on top of the SOLe suite.

Features
--------
* KRA PIN field on contacts (required for tax compliance).
* Kenya county / region selector (all 47 counties).
* 16 % VAT (standard Kenyan VAT rate) on products & invoices.
* M-Pesa payment details shown on customer invoices (Paybill / Till).
* Dedicated Kenya Shilling (KES) default currency reference data.
* Auto-set company country to Kenya on first setup.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['account', 'contacts', 'sole_mpesa'],
    'data': [
        'security/ir.model.access.csv',
        'data/kenya_counties_data.xml',
        'data/kenya_tax_data.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'icon': 'sole_kenya/static/description/icon.png',
}
