# -*- coding: utf-8 -*-
{
    "name": "Staff Money Requests",
    "summary": "Staff request small amounts (transport, airtime, advances); "
               "manager approves, finance pays, optional recovery through payroll",
    "description": """
Staff Money Requests
====================

An employee asks for a small amount of money for work: transport to a client,
airtime, lunch on a field day, a salary advance. The request goes to their
manager, who approves it or rejects it with a reason. Finance then pays it
from cash, M-Pesa or the bank, which posts the journal entry. A request marked
for payroll recovery is deducted from the employee's next payslip and closed
when that payslip is confirmed.

Who approves: the employee's manager on their employee record, or the default
approver set in Settings when they have none.
""",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "author": "Softlink Options Limited",
    "website": "https://softlinkoptions.co.ke",
    "license": "LGPL-3",
    "depends": ["hr", "account", "mail", "sole_payroll_ke"],
    "data": [
        "security/staff_request_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/request_types.xml",
        "data/salary_rule.xml",
        "report/staff_request_voucher.xml",
        "wizard/staff_request_reject_views.xml",
        "wizard/staff_request_pay_views.xml",
        "views/staff_request_type_views.xml",
        "views/staff_request_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
