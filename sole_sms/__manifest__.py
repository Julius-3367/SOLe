# -*- coding: utf-8 -*-
{
    'name': 'SOLe SMS — Onfon Media',
    'version': '19.0.1.0.0',
    'category': 'Technical/SMS',
    'summary': 'Outbound SMS via Onfon Media gateway with templates, bulk campaigns and delivery receipts',
    'description': """
SOLe SMS via Onfon Media
=========================
A standalone SMS module powered by the Onfon Media (OnfonMedia) API.

Features
--------
* Provider configuration (Onfon Media + generic HTTP providers).
* Reusable SMS templates with {placeholder} substitution.
* Ad-hoc SMS sending wizard from any partner/record.
* Bulk campaign batches — immediate or scheduled.
* Delivery receipt (DLR) webhook at /sole/sms/dlr.
* Full audit log of every outbound message.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/sms_provider_data.xml',
        'data/cron_data.xml',
        'views/sms_provider_views.xml',
        'views/sms_template_views.xml',
        'views/sms_log_views.xml',
        'wizard/send_sms_wizard_views.xml',
        'wizard/add_recipients_wizard_views.xml',
        'views/sms_batch_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
