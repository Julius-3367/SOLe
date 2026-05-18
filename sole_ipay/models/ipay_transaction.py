# -*- coding: utf-8 -*-
"""
sole.ipay.transaction — iPay payment transaction records.
"""
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SoleIpayTransaction(models.Model):
    _name = "sole.ipay.transaction"
    _description = "iPay Transaction"
    _order = "create_date desc"
    _rec_name = "order_id"

    config_id = fields.Many2one(
        "sole.ipay.config",
        string="Config",
        required=True,
        ondelete="restrict",
    )
    order_id = fields.Char(string="Order ID", required=True, index=True)
    invoice_no = fields.Char(string="Invoice Number", index=True)
    amount = fields.Float(string="Amount", digits=(16, 2))
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")
    payment_url = fields.Text(string="Payment URL", readonly=True)
    hash_value = fields.Char(string="Hash", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "URL Sent"),
            ("paid", "Paid"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        index=True,
    )
    # Callback fields
    ipay_status = fields.Char(string="iPay Status Code")
    ipay_txn_ref = fields.Char(string="iPay Txn Reference", index=True)
    raw_callback = fields.Text(string="Raw Callback")
    partner_id = fields.Many2one("res.partner", string="Customer")
    move_id = fields.Many2one("account.move", string="Journal Entry", readonly=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="config_id.company_id",
        store=True,
    )
    # Custom passthrough params
    p1 = fields.Char(string="P1")
    p2 = fields.Char(string="P2")
    p3 = fields.Char(string="P3")
    p4 = fields.Char(string="P4")

    def action_generate_url(self):
        """Generate (or regenerate) the iPay payment URL."""
        self.ensure_one()
        url, sig = self.config_id.generate_payment_url(
            order_id=self.order_id,
            invoice_no=self.invoice_no or self.order_id,
            amount=self.amount,
            phone=self.phone or "",
            email=self.email or "",
            p1=self.p1 or "",
            p2=self.p2 or "",
            p3=self.p3 or "",
            p4=self.p4 or "",
        )
        self.write({"payment_url": url, "hash_value": sig, "state": "sent"})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Payment URL Generated"),
                "message": _("Share this link with the customer to complete payment."),
                "type": "success",
            },
        }

    def action_open_payment_url(self):
        self.ensure_one()
        if not self.payment_url:
            self.action_generate_url()
        return {"type": "ir.actions.act_url", "url": self.payment_url, "target": "new"}
