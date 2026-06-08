# -*- coding: utf-8 -*-
{
    'name': 'SOLe Support ↔ Projects',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Sync support ticket assignments and stages with the Projects app',
    'description': """
Links support tickets to project tasks so assigned duties appear in the
team Support Duties project and stage or assignee changes stay in sync both ways.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['sole_support', 'project'],
    'data': [
        'data/support_project_data.xml',
        'views/support_ticket_views.xml',
        'views/project_task_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
