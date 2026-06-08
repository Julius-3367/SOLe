# -*- coding: utf-8 -*-
{
    'name': 'SOLe Kenya — Market Localisation',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Kenya-specific adaptations: KRA PIN, counties, KRA-aligned tax setup, M-Pesa invoice widgets',
    'description': """
SOLe Kenya Localisation
========================
Kenyan market adaptations built on top of Odoo's official Kenya
fiscal localisation (l10n_ke) and KRA device integration
(l10n_ke_edi_tremol), plus statutory payroll on hr_payroll_community.

Features
--------
* On first install, sets the company to Kenya / KES and loads the
  official KRA-aligned chart of accounts, VAT rates (16%/8%/0%/exempt)
  and withholding-tax templates and statutory tax reports from l10n_ke.
* KRA eTIMS / TIMS e-invoicing via the official Tremol control-unit
  device integration (l10n_ke_edi_tremol) — "Send to Tremol" button,
  CU invoice number/QR code on posted invoices, fiscal device proxy
  configuration.
* Kenya statutory payroll structure (NSSF Tier I/II, SHIF, Affordable
  Housing Levy, PAYE with the Finance Act 2023 bands and personal
  relief) on top of hr_payroll_community.
* KRA PIN field on contacts, with format validation (required for tax
  compliance).
* Kenya county / region selector (all 47 counties).
* M-Pesa payment details shown on customer invoices (Paybill / Till).
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': [
        'account', 'contacts', 'sole_mpesa',
        'l10n_ke', 'l10n_ke_edi_tremol', 'hr_payroll_community',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/kenya_counties_data.xml',
        'data/kenya_payroll_data.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'icon': 'sole_kenya/static/description/icon.png',
    'post_init_hook': 'post_init_hook',
}
