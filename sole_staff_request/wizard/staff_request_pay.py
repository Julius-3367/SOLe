# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class SoleStaffRequestPay(models.TransientModel):
    _name = "sole.staff.request.pay"
    _description = "Pay a Staff Request"

    request_id = fields.Many2one("sole.staff.request", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="request_id.company_id")
    currency_id = fields.Many2one(related="request_id.currency_id")
    amount = fields.Monetary(related="request_id.amount")
    employee_id = fields.Many2one(related="request_id.employee_id")
    journal_id = fields.Many2one(
        "account.journal", string="Pay From", required=True,
        domain="[('type', 'in', ('cash', 'bank')), ('company_id', '=', company_id)]",
        compute="_compute_journal_id", store=True, readonly=False, precompute=True,
    )
    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    reference = fields.Char(help="M-Pesa transaction code, cheque number or bank reference.")
    recover_via_payroll = fields.Boolean(
        compute="_compute_recover_via_payroll", store=True, readonly=False, precompute=True)
    recovery_date = fields.Date(
        string="Recover from Payslip of",
        default=lambda self: fields.Date.context_today(self) + relativedelta(months=1, day=1),
        help="Deducted from the first payslip ending on or after this date.",
    )

    @api.depends("request_id")
    def _compute_journal_id(self):
        for wizard in self:
            wizard.journal_id = wizard.request_id.company_id.sole_request_journal_id

    @api.depends("request_id")
    def _compute_recover_via_payroll(self):
        for wizard in self:
            wizard.recover_via_payroll = wizard.request_id.recover_via_payroll

    def action_pay(self):
        self.request_id._do_pay(
            self.journal_id, self.payment_date, self.reference,
            self.recover_via_payroll, self.recovery_date,
        )
        return {"type": "ir.actions.act_window_close"}
