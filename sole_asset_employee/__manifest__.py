# -*- coding: utf-8 -*-
{
    'name': 'SOLe Asset Custodians',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Assign each fixed asset to the employee who holds it',
    'description': """
SOLe Asset Custodians
=====================
* An Assigned Employee on every fixed asset, editable at any time (custodians
  change), with each change recorded in the asset's chatter.
* The employee's department is kept with the asset for filtering and grouping.
* An Assets button on the employee form listing what they hold, for handover
  and exit clearance.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['base_accounting_kit', 'hr'],
    'data': [
        'views/account_asset_views.xml',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
