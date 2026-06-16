# -*- coding: utf-8 -*-
{
    'name': 'SOLe eTIMS — KRA e-Invoice Integration',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'KRA eTIMS VSCU API integration for community Odoo — sends invoices to KRA electronically',
    'description': """
SOLe eTIMS Integration
======================
Connects to the KRA eTIMS (Electronic Tax Invoice Management System) API
for businesses that use a Virtual Sales Control Unit (VSCU) instead of
the Tremol G03 hardware device.

Features
--------
* Send to eTIMS button on posted customer invoices
* Builds and submits KRA-compliant invoice payload (VSCU schema)
* Stores KRA receipt number, QR code and sign date on the invoice
* Works alongside l10n_ke_edi_tremol — when eTIMS is enabled the Tremol
  button is automatically hidden (same behaviour as the Enterprise OSCU)
* Sandbox and production API URL configurable per company
* Standard Kenya VAT type codes: A (16%), B (8%), C (zero-rated), E (exempt)
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['l10n_ke', 'l10n_ke_edi_tremol'],
    'data': [
        'data/etims_sequence.xml',
        'views/res_config_settings_view.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
