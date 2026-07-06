# -*- coding: utf-8 -*-
{
    'name': 'SOLe M-Pesa Integration',
    'version': '19.0.1.2.0',
    'category': 'Accounting/Payment',
    'summary': 'M-Pesa STK Push (Lipa Na M-Pesa) and C2B Paybill integration via Safaricom Daraja API',
    'description': """
SOLe M-Pesa Integration
========================
Integrates Safaricom M-Pesa Daraja API into Odoo 19.

Features
--------
* STK Push (Lipa Na M-Pesa Online) — initiate payment requests to customer phones.
* C2B Paybill — register validation/confirmation URLs and receive incoming payments.
* Transaction log with status tracking (pending → completed/failed).
* Sandbox / production environment switching.
* Automatic access token refresh with caching.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/mpesa_config_data.xml',
        'data/cron_data.xml',
        'views/mpesa_config_views.xml',
        'views/mpesa_transaction_views.xml',
        'wizard/stk_push_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
