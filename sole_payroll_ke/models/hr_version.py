# -*- coding: utf-8 -*-
"""Kenyan payroll fields on the employee's contract version.

Odoo 19 keeps contract terms on hr.version, and hr_payroll_community hands
that record to the salary rules as `contract`. These fields started life on
the old hr.contract shim, which the rules never see; that is why every rule
reading them failed.

hr.employee inherits hr.version, so everything here is also editable from the
employee form and writes through to the current version.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrVersion(models.Model):
    _inherit = "hr.version"

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
    ke_helb = fields.Monetary(
        string="HELB Repayment",
        help="Monthly HELB loan repayment as set by HELB's deduction notice. "
             "Deducted every month until changed. A one-off adjustment can "
             "still be entered as a HELB input on a single payslip.",
    )
    ke_recurring_line_ids = fields.One2many(
        "sole.payroll.recurring.line", "version_id",
        string="Fixed Deductions and Allowances",
        help="Amounts that repeat every month: SACCO, staff loan, welfare, "
             "a fixed taxable allowance. Each applies between its own dates.",
    )

    ke_is_secondary = fields.Boolean(
        string="Secondary Employment",
        help="Tick when this is not the employee's main job. Secondary "
             "employment is taxed at a flat rate with no personal relief, and "
             "statutory deductions are handled by the primary employer.",
    )

    # ── Helpers exposed to salary rules ──────────────────────────────────────
    def rule_param(self, code, date=None):
        """Look up a payroll rate parameter from inside a salary rule.

        `contract` is one of the few real recordsets available in a rule's
        evaluation context, so this is where rate lookups have to live — the
        payslip object rules receive is a thin wrapper that cannot take
        method calls.

        Always pass the payslip date. Without it the current rate is used,
        which silently rewrites history when an old payslip is recomputed.
        """
        return self.env["sole.payroll.parameter"].get_value(code, date or None)

    def ke_recurring_total(self, kind, date_from, date_to):
        """Total of the fixed lines of `kind` in force during the period."""
        self.ensure_one()
        lines = self.ke_recurring_line_ids.filtered(
            lambda l: l.kind == kind
            and l.date_from <= date_to
            and (not l.date_to or l.date_to >= date_from)
        )
        return sum(lines.mapped("amount"))


class SolePayrollRecurringLine(models.Model):
    _name = "sole.payroll.recurring.line"
    _description = "Fixed Monthly Deduction or Allowance"
    _order = "kind, date_from"

    version_id = fields.Many2one(
        "hr.version", required=True, ondelete="cascade", index=True
    )
    employee_id = fields.Many2one(related="version_id.employee_id", store=True)
    name = fields.Char(
        string="Description", required=True,
        help="Shown to payroll staff, e.g. 'Stima SACCO' or 'Staff loan, June 2026'.",
    )
    kind = fields.Selection(
        [("deduction", "Deduction"), ("allowance", "Taxable Allowance")],
        required=True, default="deduction",
    )
    amount = fields.Monetary(required=True, help="Monthly amount.")
    currency_id = fields.Many2one(related="version_id.currency_id")
    date_from = fields.Date(
        string="From", required=True, default=fields.Date.context_today
    )
    date_to = fields.Date(
        string="Until", help="Last month it applies. Leave empty to continue until removed."
    )

    @api.constrains("amount", "date_from", "date_to")
    def _check_line(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("'%s' must have a positive amount.") % line.name)
            if line.date_to and line.date_to < line.date_from:
                raise ValidationError(_("'%s' ends before it starts.") % line.name)
