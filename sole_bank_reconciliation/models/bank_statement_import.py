# -*- coding: utf-8 -*-
"""
sole.bank.statement.import — Bank statement import session.
Holds a batch of imported lines before reconciliation.
"""
from odoo import _, api, fields, models


class SoleBankStatementImport(models.Model):
    _name = "sole.bank.statement.import"
    _description = "Bank Statement Import"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Import Name", required=True)
    journal_id = fields.Many2one(
        "account.journal",
        string="Bank Journal",
        required=True,
        domain=[("type", "=", "bank")],
    )
    bank_format = fields.Selection(
        [
            ("mpesa", "M-Pesa"),
            ("equity", "Equity Bank"),
            ("kcb", "KCB Bank"),
            ("coop", "Co-operative Bank"),
            ("generic", "Generic CSV"),
        ],
        string="Statement Format",
        required=True,
        default="generic",
    )
    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")
    state = fields.Selection(
        [("draft", "Imported"), ("reconciled", "Reconciled"), ("cancelled", "Cancelled")],
        string="Status",
        default="draft",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        "sole.bank.recon.line", "import_id", string="Statement Lines"
    )

    # Summary stats
    total_lines = fields.Integer(string="Total Lines", compute="_compute_stats", store=True)
    matched_lines = fields.Integer(string="Matched", compute="_compute_stats", store=True)
    unmatched_lines = fields.Integer(string="Unmatched", compute="_compute_stats", store=True)
    total_debit = fields.Float(string="Total Debit", compute="_compute_stats", store=True, digits=(16, 2))
    total_credit = fields.Float(string="Total Credit", compute="_compute_stats", store=True, digits=(16, 2))

    @api.depends("line_ids", "line_ids.state")
    def _compute_stats(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_lines = len(lines)
            rec.matched_lines = len(lines.filtered(lambda l: l.state == "matched"))
            rec.unmatched_lines = len(lines.filtered(lambda l: l.state == "unmatched"))
            rec.total_debit = sum(l.debit for l in lines)
            rec.total_credit = sum(l.credit for l in lines)

    def action_mark_reconciled(self):
        self.state = "reconciled"

    def action_cancel(self):
        self.state = "cancelled"
