# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sole_request_default_approver_id = fields.Many2one(
        related="company_id.sole_request_default_approver_id", readonly=False)
    sole_request_finance_user_id = fields.Many2one(
        related="company_id.sole_request_finance_user_id", readonly=False)
    sole_request_journal_id = fields.Many2one(
        related="company_id.sole_request_journal_id", readonly=False)
    sole_staff_advance_account_id = fields.Many2one(
        related="company_id.sole_staff_advance_account_id", readonly=False)

    def set_values(self):
        super().set_values()
        # The payroll deduction clears the advance, so the payroll entry has to
        # credit the same account the payment debited
        rule = self.env.ref("sole_staff_request.rule_staff_advance", raise_if_not_found=False)
        account = self.company_id.sole_staff_advance_account_id
        if rule and account and "account_credit_id" in rule._fields:
            rule.sudo().account_credit_id = account
