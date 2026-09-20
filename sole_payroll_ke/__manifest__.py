# -*- coding: utf-8 -*-
{
    "name": "Kenyan Payroll (SOLe)",
    "summary": "Kenyan statutory payroll rules for hr_payroll_community",
    "description": """
Kenyan Payroll
==============

Salary rules for Kenyan payroll built on ``hr_payroll_community``: NSSF
Tier I and II, SHIF, the Affordable Housing Levy, PAYE with banded rates,
personal and insurance reliefs, and the taxed/untaxed treatment of
allowances.

Rates are not written into the rules. Each one is a dated parameter record,
so when a Finance Act changes a band or a ceiling an accountant adds a new
value with its effective date. Payslips for earlier periods continue to use
the rate that applied at the time, so re-running an old payslip still
reproduces the figure that was actually paid.

Scope
-----
This module covers the treatment in force from 2026. The transitional rules
around the introduction of the housing levy in 2024 and the replacement of
NHIF by SHIF are not reproduced, because this system holds no payroll
history from that period.

Before relying on it
--------------------
Run a full month in parallel against payslips whose correct figures are
already known, and reconcile every line. Payroll errors are not bugs to be
fixed next sprint — they are underpaid staff and short remittances to KRA.
""",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Payroll",
    "author": "Softlink Options Limited",
    "website": "https://softlinkoptions.co.ke",
    "license": "LGPL-3",
    "depends": [
        "hr_payroll_community",
        "hr_contract",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/salary_rule_categories.xml",
        "data/payroll_parameters.xml",
        "data/salary_rules.xml",
        "data/payroll_structure.xml",
        "views/payroll_parameter_views.xml",
        "views/hr_contract_views.xml",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
}
