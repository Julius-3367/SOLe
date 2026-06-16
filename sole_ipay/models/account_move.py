# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    ipay_transaction_ids = fields.One2many(
        "sole.ipay.transaction",
        "invoice_id",
        string="iPay Transactions",
        readonly=True,
    )
    ipay_transaction_count = fields.Integer(
        string="iPay Payments",
        compute="_compute_ipay_transaction_count",
    )

    def _compute_ipay_transaction_count(self):
        for move in self:
            move.ipay_transaction_count = len(move.ipay_transaction_ids)

    def action_view_ipay_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("iPay Transactions"),
            "res_model": "sole.ipay.transaction",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id},
        }

    def action_request_ipay_payment(self):
        """Create an iPay payment request for this invoice.

        - Finds or reuses any existing draft/sent transaction.
        - Auto-populates amount, phone, email from the invoice.
        - Generates the payment URL.
        - Emails it to the customer if an email address is available.
        - Opens the transaction form so the user can see the URL.
        """
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(_("iPay payment can only be requested for customer invoices."))
        if self.state != "posted":
            raise UserError(_("Confirm the invoice before requesting a payment."))
        if self.payment_state == "paid":
            raise UserError(_("This invoice is already fully paid."))
        if self.amount_residual <= 0:
            raise UserError(_("There is no outstanding amount on this invoice."))

        config = self.env["sole.ipay.config"].search([("is_active", "=", True)], limit=1)
        if not config:
            raise UserError(
                _("No active iPay configuration found. "
                  "Go to Accounting → iPay → Configuration and set one up first.")
            )

        # Reuse an existing pending transaction rather than creating duplicates
        existing = self.env["sole.ipay.transaction"].search(
            [("invoice_id", "=", self.id), ("state", "in", ["draft", "sent"])],
            limit=1,
        )
        if existing:
            return {
                "type": "ir.actions.act_window",
                "name": _("iPay Transaction"),
                "res_model": "sole.ipay.transaction",
                "res_id": existing.id,
                "view_mode": "form",
                "views": [(False, "form")],
                "target": "current",
            }

        tx = self.env["sole.ipay.transaction"].create({
            "config_id": config.id,
            "order_id": self.name,
            "invoice_no": self.name,
            "amount": self.amount_residual,
            "phone": self.partner_id.phone or self.partner_id.mobile or "",
            "email": self.partner_id.email or "",
            "partner_id": self.partner_id.id,
            "invoice_id": self.id,
        })

        tx._do_generate_url()

        if tx.email:
            try:
                tx._do_send_url_email()
            except Exception:
                _logger.exception("iPay: could not send email for transaction %s", tx.order_id)

        return {
            "type": "ir.actions.act_window",
            "name": _("iPay Transaction"),
            "res_model": "sole.ipay.transaction",
            "res_id": tx.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
