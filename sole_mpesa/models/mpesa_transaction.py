# -*- coding: utf-8 -*-
"""
sole.mpesa.transaction — M-Pesa STK Push and C2B transaction records.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Daraja STK Push query ResultCode meaning the user cancelled the prompt.
STK_CANCELLED_RESULT_CODE = "1032"


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

    def action_view_payment(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No journal entry linked to this transaction."))
        return self.move_id.get_formview_action()

    def action_bulk_create_journal_entries(self):
        """Create journal entries for all selected completed transactions that don't have one yet."""
        created = 0
        skipped = 0
        for tx in self:
            if tx.state != "completed":
                skipped += 1
                continue
            if tx.move_id:
                skipped += 1
                continue
            try:
                tx.action_create_journal_entry()
                created += 1
            except UserError as exc:
                _logger.warning(
                    "M-Pesa bulk post failed for %s: %s",
                    tx.checkout_request_id, exc,
                )
                skipped += 1
        msg = _("%d journal entr%s created.") % (created, "ies" if created != 1 else "y")
        if skipped:
            msg += " " + _("%d skipped (not completed or already posted).") % skipped
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Journal Entries"),
                "message": msg,
                "type": "success" if created else "warning",
                "sticky": False,
            },
        }

    def action_create_journal_entry(self):
        """Create an inbound payment for completed M-Pesa transactions."""
        self.ensure_one()
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
            "payment_reference": self.mpesa_receipt_number or self.checkout_request_id,
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

    # ── Status polling / auto-reconciliation ──────────────────────────────────
    def action_check_status(self):
        """Query Daraja for the latest status of pending STK Push transactions.

        Safe to call on any selection: non-pending and C2B records are skipped.
        Used by the "Check Status" button and by :meth:`_cron_auto_reconcile`.
        """
        for tx in self:
            if tx.transaction_type != "stk_push" or tx.state != "pending":
                continue
            if not tx.checkout_request_id:
                continue
            try:
                result = tx.config_id.action_query_stk_status(tx.checkout_request_id)
            except UserError as exc:
                _logger.warning(
                    "M-Pesa status check failed for %s: %s",
                    tx.checkout_request_id, exc,
                )
                continue
            result_code = result.get("ResultCode")
            if result_code is None:
                # Daraja responds with an errorCode (no ResultCode) while the
                # transaction is still being processed — leave as pending.
                continue
            result_code = str(result_code)
            vals = {
                "result_code": result_code,
                "result_desc": result.get("ResultDesc", ""),
            }
            if result_code == "0":
                vals["state"] = "completed"
            elif result_code == STK_CANCELLED_RESULT_CODE:
                vals["state"] = "cancelled"
            else:
                vals["state"] = "failed"
            tx.write(vals)

    @api.model
    def _cron_auto_reconcile(self):
        """Periodic job: refresh pending STK statuses and post payments.

        1. For pending STK Push transactions, poll Daraja for the result.
        2. For any completed transaction without a journal entry yet
           (including ones just confirmed above, and C2B confirmations
           received via the webhook), create the inbound payment and
           reconcile it against a matching invoice.
        """
        pending = self.search([
            ("transaction_type", "=", "stk_push"),
            ("state", "=", "pending"),
        ])
        if pending:
            pending.action_check_status()

        completed = self.search([
            ("state", "=", "completed"),
            ("move_id", "=", False),
        ])
        for tx in completed:
            try:
                tx.action_create_journal_entry()
            except UserError as exc:
                _logger.warning(
                    "M-Pesa auto-reconcile failed for %s: %s",
                    tx.checkout_request_id, exc,
                )


