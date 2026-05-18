# -*- coding: utf-8 -*-
"""
sole.mpesa.transaction — M-Pesa STK Push and C2B transaction records.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SoleMpesaTransaction(models.Model):
    _name = "sole.mpesa.transaction"
    _description = "M-Pesa Transaction"
    _order = "create_date desc"
    _rec_name = "checkout_request_id"

    config_id = fields.Many2one(
        "sole.mpesa.config",
        string="Config",
        required=True,
        ondelete="restrict",
    )
    transaction_type = fields.Selection(
        [("stk_push", "STK Push"), ("c2b", "C2B Paybill")],
        string="Type",
        required=True,
    )
    phone = fields.Char(string="Phone Number")
    amount = fields.Float(string="Amount", digits=(16, 2))
    account_ref = fields.Char(string="Account Reference")
    transaction_desc = fields.Char(string="Description")
    merchant_request_id = fields.Char(string="Merchant Request ID", index=True)
    checkout_request_id = fields.Char(string="Checkout / Request ID", index=True)
    mpesa_receipt_number = fields.Char(string="M-Pesa Receipt No.", index=True)
    mpesa_transaction_date = fields.Char(string="M-Pesa Tx Date")
    result_code = fields.Char(string="Result Code")
    result_desc = fields.Char(string="Result Description")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        index=True,
    )
    raw_payload = fields.Text(string="Raw Callback Payload")
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        help="Accounting entry created for this transaction.",
        readonly=True,
    )
    partner_id = fields.Many2one("res.partner", string="Customer")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="config_id.company_id",
        store=True,
    )

    def action_mark_completed(self):
        self.write({"state": "completed"})

    def action_mark_failed(self):
        self.write({"state": "failed"})

    def action_create_journal_entry(self):
        """Create an inbound payment for completed M-Pesa transactions."""
        self.ensure_one()
        from odoo.exceptions import UserError
        if self.state != "completed":
            raise UserError(_("Only completed transactions can be posted."))
        if self.move_id:
            return self.move_id.get_formview_action()
        journal = self.config_id.account_journal_id
        if not journal:
            raise UserError(_("Please set a Payment Journal on the M-Pesa configuration."))

        # Find inbound payment method line
        inbound_lines = journal.inbound_payment_method_line_ids
        payment_method_line = inbound_lines[:1] if inbound_lines else False

        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_id.id if self.partner_id else False,
            "amount": self.amount,
            "date": fields.Date.today(),
            "ref": self.mpesa_receipt_number or self.checkout_request_id,
            "journal_id": journal.id,
            "payment_method_line_id": payment_method_line.id if payment_method_line else False,
            "memo": f"M-Pesa {self.transaction_type.upper()} — {self.account_ref or self.phone}",
        })
        payment.action_post()
        self.move_id = payment.move_id

        # Auto-reconcile with open customer invoice if account_ref matches invoice number
        if self.partner_id and self.account_ref:
            invoice = self.env["account.move"].search([
                ("partner_id", "=", self.partner_id.id),
                ("state", "=", "posted"),
                ("payment_state", "in", ["not_paid", "partial"]),
                ("move_type", "=", "out_invoice"),
                "|",
                ("name", "=", self.account_ref),
                ("ref", "=", self.account_ref),
            ], limit=1)
            if invoice:
                (payment.move_id + invoice).line_ids.filtered(
                    lambda l: l.account_type in ("asset_receivable", "liability_payable")
                    and not l.reconciled
                ).reconcile()

        return payment.move_id.get_formview_action()


