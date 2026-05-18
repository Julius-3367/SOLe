# -*- coding: utf-8 -*-
{
    'name': 'SOLe iPay Payment Gateway',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'iPay Kenya payment gateway integration — generate payment links and receive webhook callbacks',
    'description': """
SOLe iPay Integration
======================
Integrates the iPay Kenya payment gateway into Odoo 19.

Features
--------
* Generate signed iPay payment URLs for invoices.
* Webhook endpoint to receive payment confirmation callbacks.
* Transaction log with status tracking.
* Configurable sandbox / live environments.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/ipay_config_data.xml',
        'views/ipay_config_views.xml',
        'views/ipay_transaction_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
