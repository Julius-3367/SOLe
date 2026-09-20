# -*- coding: utf-8 -*-
"""Kenyan payroll fields on the employment contract.

These mirror the fields Odoo's own Kenyan localisation puts on a contract, so
the salary rules read the same way. The `l10n_ke_` prefix is dropped in favour
of `ke_`, since this is our module and not Odoo's localisation — keeping their
prefix would imply their maintenance.
"""
from odoo import _, api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    # ── Allowances ───────────────────────────────────────────────────────────
    # Each of these is untaxed up to a statutory ceiling and taxed above it,
    # which is why the rules come in pairs. The ceilings are parameters, not
    # constants here.
    ke_food_allowance = fields.Monetary(
        string="Food Allowance",
        help="Untaxed up to the statutory monthly limit; fully taxable if it "
             "exceeds it.",
    )
    ke_airtime_allowance = fields.Monetary(
        string="Airtime Allowance",
        help="Untaxed up to the statutory monthly limit; fully taxable if it "
             "exceeds it.",
    )
    ke_pension_allowance = fields.Monetary(
        string="Pension Allowance",
        help="Untaxed up to the statutory limit. Only the excess is taxed.",
    )
    ke_commuter_allowance = fields.Monetary(
        string="Commuter Allowance", help="Fully taxable."
    )

    ke_housing_allowance_unit = fields.Selection(
        [("fixed", "Fixed Amount"), ("percentage", "Percentage of Basic")],
        string="Housing Allowance Type",
        default="fixed",
    )
    ke_housing_allowance_fixed = fields.Monetary(string="Housing Allowance")
    ke_housing_allowance_percentage = fields.Float(
        string="Housing Allowance (%)",
        help="Percentage of basic salary, used when the type is Percentage.",
    )

    # ── Contributions and deductions ─────────────────────────────────────────
    ke_pension_contribution = fields.Monetary(
        string="Pension Contribution",
        help="Employee contribution to a registered pension scheme. Combined "
             "with NSSF this is deductible from taxable pay, up to the "
             "statutory maximum.",
    )
    ke_voluntary_medical_insurance = fields.Monetary(
        string="Voluntary Medical Insurance", help="Attracts insurance relief."
    )
    ke_life_insurance = fields.Monetary(
        string="Life Insurance", help="Attracts insurance relief."
    )
    ke_education = fields.Monetary(
        string="Education Policy", help="Attracts insurance relief."
    )
    ke_is_li_managed_by_employee = fields.Boolean(
        string="Life Insurance Paid by Employee",
        help="Tick when the employee pays the premium directly. Relief still "
             "applies, but nothing is deducted from their pay.",
    )

    ke_is_secondary = fields.Boolean(
        string="Secondary Employment",
        help="Tick when this is not the employee's main job. Secondary "
             "employment is taxed at a flat rate with no personal relief, and "
             "statutory deductions are handled by the primary employer.",
    )

    # ── Helper exposed to salary rules ───────────────────────────────────────
    def rule_param(self, code, date=None):
        """Look up a payroll rate parameter from inside a salary rule.

        `contract` is one of the few real recordsets available in a rule's
        evaluation context, so hanging this method here is what makes rate
        lookups possible at all — the payslip object rules receive is a thin
        wrapper that cannot take method calls.

        Always pass the payslip date. Without it the current rate is used,
        which silently rewrites history when an old payslip is recomputed.
        """
        return self.env["sole.payroll.parameter"].get_value(code, date or None)
