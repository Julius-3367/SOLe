# -*- coding: utf-8 -*-
{
    'name': 'Employee Contracts',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage employee contracts (community shim for Odoo 19)',
    'depends': ['hr'],
    'data': [
        'security/hr_contract_security.xml',
        'security/ir.model.access.csv',
        'views/hr_contract_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
