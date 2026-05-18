# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SoleBankReconLine(models.Model):
    _name = "sole.bank.recon.line"
    _description = "Bank Reconciliation Line"
    _order = "transaction_date, id"
    _rec_name = "description"

    import_id = fields.Many2one(
        "sole.bank.statement.import",
        string="Statement",
        required=True,
        ondelete="cascade",
    )
    transaction_date = fields.Date(string="Date", required=True)
    description = fields.Char(string="Description")
    ref = fields.Char(string="Reference / Receipt No.", index=True)
    debit = fields.Float(string="Debit (Out)", digits=(16, 2), default=0.0)
    credit = fields.Float(string="Credit (In)", digits=(16, 2), default=0.0)
    balance = fields.Float(string="Running Balance", digits=(16, 2))
    state = fields.Selection(
        [
            ("unmatched", "Unmatched"),
            ("matched", "Matched"),
            ("ignored", "Ignored"),
        ],
        string="Status",
        default="unmatched",
        index=True,
    )
    matched_move_line_id = fields.Many2one(
        "account.move.line",
        string="Matched Journal Entry",
        help="Odoo journal entry line matched to this bank line.",
    )
    notes = fields.Char(string="Notes")

    def action_match(self):
        """Open a match dialog (simple: mark as matched)."""
        self.state = "matched"

    def action_ignore(self):
        self.state = "ignored"

    def action_unmatch(self):
        self.write({"state": "unmatched", "matched_move_line_id": False})
