# -*- coding: utf-8 -*-
from odoo import fields, models


class SoleStaffRequestType(models.Model):
    _name = "sole.staff.request.type"
    _description = "Staff Request Type"
    _order = "sequence, name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company,
        help="Leave empty to offer this type in every company.",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)
    expense_account_id = fields.Many2one(
        "account.account", string="Expense Account", check_company=True,
        help="Debited when a request of this type is paid, unless it is being "
             "recovered through payroll.",
    )
    recover_via_payroll = fields.Boolean(
        string="Recover through Payroll by Default",
        help="Tick for salary advances. Finance can still change it on each payment.",
    )
    max_amount = fields.Monetary(
        string="Maximum per Request",
        help="Requests above this cannot be submitted. Zero means no limit.",
    )
    description = fields.Text(help="Shown to staff when they choose this type.")
