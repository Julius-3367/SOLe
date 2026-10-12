# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sole_request_default_approver_id = fields.Many2one(
        "res.users", string="Default Approver",
        domain="[('share', '=', False)]",
        help="Approves requests from staff who have no manager on their "
             "employee record, and requests from managers themselves.",
    )
    sole_request_finance_user_id = fields.Many2one(
        "res.users", string="Finance Officer",
        domain="[('share', '=', False)]",
        help="Gets an activity to pay each approved request.",
    )
    sole_request_journal_id = fields.Many2one(
        "account.journal", string="Default Payment Journal",
        domain="[('type', 'in', ('cash', 'bank')), ('company_id', '=', id)]",
        help="Suggested when finance pays a request; can be changed per payment.",
    )
    sole_staff_advance_account_id = fields.Many2one(
        "account.account", string="Staff Advances Account",
        domain="[('account_type', 'in', ('asset_current', 'asset_receivable'))]",
        help="Debited instead of the request type's expense account when a "
             "request will be recovered through payroll, and credited by the "
             "payroll deduction that recovers it.",
    )
