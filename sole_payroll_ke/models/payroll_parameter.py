# -*- coding: utf-8 -*-
"""Date-versioned payroll rate parameters.

Kenyan statutory rates change with every Finance Act — PAYE bands move, NSSF
tiers are revised, NHIF became SHIF. Writing those numbers into salary rule
formulas would mean a developer every time a rate changes, and a payroll that
is quietly wrong whenever nobody notices.

Instead each rate lives here as data, with the date it takes effect. An
accountant adds a new value with a new start date; payslips for earlier months
keep using the old value, so re-running an old payslip still produces the
figure that was actually paid.

The design follows Odoo Enterprise's `hr.rule.parameter`, so if Softlink ever
moves to Enterprise the concepts carry over directly.
"""
import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SolePayrollParameter(models.Model):
    _name = "sole.payroll.parameter"
    _description = "Payroll Rate Parameter"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Referenced from salary rules as "
             "contract.rule_param('code', payslip.date_to)",
    )
    note = fields.Text(
        string="Notes",
        help="Where this rate comes from — the Act, circular or KRA "
             "guidance. Worth filling in: whoever updates it next will not "
             "have the context you have now.",
    )
    value_ids = fields.One2many(
        "sole.payroll.parameter.value", "parameter_id", string="Values"
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )

    _sql_constraints = [
        ("code_uniq", "unique(code, company_id)",
         "A payroll parameter with this code already exists."),
    ]

    @api.model
    def get_value(self, code, date=None):
        """Return the value of `code` in force on `date`.

        Raises rather than returning a default. A silently missing rate would
        produce a payslip that looks fine and is wrong, which is worse than a
        payslip that refuses to compute.
        """
        if not date:
            date = fields.Date.context_today(self)
        param = self.sudo().search([("code", "=", code)], limit=1)
        if not param:
            raise UserError(
                _("No payroll parameter is defined with the code '%s'.") % code
            )
        value = param.value_ids.filtered(
            lambda v: v.date_from <= date
        ).sorted("date_from", reverse=True)[:1]
        if not value:
            raise UserError(
                _("The payroll parameter '%(code)s' has no value in force on "
                  "%(date)s. Its earliest value starts later than the payslip "
                  "period.", code=code, date=date)
            )
        return value.parsed_value


class SolePayrollParameterValue(models.Model):
    _name = "sole.payroll.parameter.value"
    _description = "Payroll Rate Parameter Value"
    _order = "date_from desc"

    parameter_id = fields.Many2one(
        "sole.payroll.parameter", required=True, ondelete="cascade", index=True
    )
    code = fields.Char(related="parameter_id.code", store=True)
    date_from = fields.Date(
        string="Effective From", required=True,
        help="The first day this value applies. Payslips dated before this "
             "keep using the previous value.",
    )
    value = fields.Char(
        required=True,
        help="A number, or a Python literal for banded rates — for example "
             "a list of (upper bound, rate) pairs for the PAYE bands.",
    )

    @api.constrains("value")
    def _check_value(self):
        for record in self:
            try:
                ast.literal_eval(record.value)
            except (ValueError, SyntaxError):
                raise ValidationError(
                    _("'%s' is not a valid value. Enter a number, or a list "
                      "such as [(24000, 0.1), (8333, 0.25)].") % record.value
                )

    @property
    def parsed_value(self):
        """The stored text as a Python value.

        literal_eval is used rather than eval: it accepts numbers, strings,
        tuples and lists but will not execute anything, so a parameter can
        never become a way to run code inside payroll.
        """
        self.ensure_one()
        return ast.literal_eval(self.value)
