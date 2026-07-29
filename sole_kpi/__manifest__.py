# -*- coding: utf-8 -*-
{
    'name': 'SOLe KPI & Scorecard',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Balanced Scorecard, KPI tracking, and Tender management for Softlink Options Limited',
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/kpi_categories.xml',
        'data/kpi_roles.xml',
        'data/kpi_indicators.xml',
        'views/kpi_views.xml',
        'views/tender_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sole_kpi/static/src/css/sole_kpi.css',
            'sole_kpi/static/src/xml/kpi_dashboard.xml',
            'sole_kpi/static/src/js/kpi_dashboard.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
