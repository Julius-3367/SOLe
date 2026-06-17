# -*- coding: utf-8 -*-
{
    'name': 'SOLe Support Center',
    'version': '19.0.1.2.0',
    'category': 'Services/Helpdesk',
    'summary': 'Customer support ticket management — stages, categories, SLA tracking and portal submission',
    'description': """
SOLe Support Center
====================
A lightweight helpdesk/support-ticket system built for Odoo 19.

Features
--------
* Support tickets with stage pipeline (Backlog → In Progress → Complete).
* Categories and priority levels.
* Assignment to internal users.
* SLA deadline tracking.
* Customer portal page for submitting and tracking tickets.
* Email notification on ticket creation and stage changes.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'data/support_stage_data.xml',
        'data/support_category_data.xml',
        'data/mail_template_data.xml',
        'views/support_stage_views.xml',
        'views/support_category_views.xml',
        'views/support_ticket_views.xml',
        'views/menus.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
