# -*- coding: utf-8 -*-
{
    'name': 'SOLe Bank Reconciliation',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Bank',
    'summary': 'Enhanced bank statement import and reconciliation for Kenyan banks — CSV/Excel import with M-Pesa, Equity, KCB and Co-op statement formats',
    'description': """
SOLe Bank Reconciliation
=========================
Extends Odoo 19's native bank reconciliation with:

* CSV import wizard supporting common Kenyan bank statement formats:
  - M-Pesa statement (CSV export from Safaricom)
  - Equity Bank statement
  - KCB Bank statement
  - Co-operative Bank statement
  - Generic CSV (Date, Description, Debit, Credit, Balance)
* Auto-detection of statement format.
* Duplicate detection based on transaction reference.
* Reconciliation summary dashboard with matched/unmatched counts.
* Manual reconciliation notes and status per statement line.
    """,
    'author': 'SOLe',
    'website': 'https://sole.co.ke',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/bank_statement_import_views.xml',
        'views/bank_recon_line_views.xml',
        'wizard/bank_import_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
