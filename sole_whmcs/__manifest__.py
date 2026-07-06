# -*- coding: utf-8 -*-
{
    'name': 'SOLe WHMCS Connector',
    'version': '19.0.1.1.0',
    'category': 'Sales/CRM',
    'summary': 'Sync clients and invoices between WHMCS billing platform and Odoo',
    'description': """
SOLe WHMCS Connector
=====================
One-way integration: WHMCS → Odoo 19.

Features
--------
* Configure WHMCS API URL, API Identifier and Secret.
* Import WHMCS clients as Odoo partners with country mapping.
* Import WHMCS invoices as Odoo customer invoices (draft by default).
* Auto-post Paid invoices option; Cancelled/Refunded invoices auto-cancelled.
* Partner deduplication via dedicated whmcs_client_id field (not comment field).
* Manual sync wizard and scheduled automatic sync.
* Sync log to track import history and errors.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account', 'product'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/whmcs_config_views.xml',
        'views/whmcs_sync_log_views.xml',
        'wizard/whmcs_sync_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
