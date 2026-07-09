# -*- coding: utf-8 -*-
{
    'license': 'LGPL-3',
    'name': 'Document Management System',
    'summary': 'Hierarchical document and knowledge-base management with tags, favorites, and file attachments',
    'author': 'Softlink Options',
    'website': 'https://softlinkoptions.co.ke',
    'category': 'Document Management',
    'version': '19.0.2.0.0',
    'depends': ['mail'],
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'views/document.xml',
        'views/document_tag.xml',
    ],
    'images': [
        'static/description/main_screenshot.png',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
