# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SoleIpayTransaction(models.Model):
    _name = "sole.ipay.transaction"
    _description = "iPay Transaction"
    _order = "create_date desc"
    _rec_name = "order_id"
    _inherit = ["mail.thread"]

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
        tracking=True,
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
    p1 = fields.Char(string="P1")
    p2 = fields.Char(string="P2")
    p3 = fields.Char(string="P3")
    p4 = fields.Char(string="P4")

    def action_generate_url(self):
        """Generate the signed iPay payment URL and reload the form so it is immediately visible."""
        self.ensure_one()
        if not self.config_id:
            raise UserError(_("Select an iPay configuration before generating a URL."))
        if not self.amount or self.amount <= 0:
            raise UserError(_("Enter a valid amount before generating a URL."))
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
        _logger.info("iPay payment URL generated for order %s", self.order_id)
        # Show sticky notification and reload the form so the URL becomes visible
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Payment URL Ready"),
                "message": _("The payment link has been generated. Copy it from the form below or send it to the customer by email."),
                "type": "success",
                "sticky": True,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": self._name,
                    "res_id": self.id,
                    "view_mode": "form",
                    "target": "current",
                },
            },
        }

    def action_open_payment_url(self):
        """Open the payment page in a new browser tab."""
        self.ensure_one()
        if not self.payment_url:
            raise UserError(_("Generate the payment URL first."))
        return {"type": "ir.actions.act_url", "url": self.payment_url, "target": "new"}

    def action_send_url_email(self):
        """Email the payment link directly to the customer."""
        self.ensure_one()
        if not self.payment_url:
            raise UserError(_("Generate the payment URL before sending it."))
        if not self.email:
            raise UserError(_("Enter a customer email address before sending."))
        self.env["mail.mail"].sudo().create({
            "subject": _("Your Payment Link — Order %s") % self.order_id,
            "body_html": _(
                "<p>Dear %(name)s,</p>"
                "<p>Please use the link below to complete your payment of <strong>%(currency)s %(amount).2f</strong>:</p>"
                "<p><a href='%(url)s' style='background:#017e84;color:#fff;padding:10px 20px;"
                "text-decoration:none;border-radius:4px;display:inline-block;margin:8px 0;'>"
                "Pay Now</a></p>"
                "<p>Or copy this link: <br/><code>%(url)s</code></p>"
                "<p>Reference: %(order)s</p>"
            ) % {
                "name": self.partner_id.name if self.partner_id else _("Customer"),
                "currency": self.config_id.currency,
                "amount": self.amount,
                "url": self.payment_url,
                "order": self.order_id,
            },
            "email_to": self.email,
            "email_from": self.env.company.email or self.env.user.email,
        }).send()
        self.message_post(
            body=_("Payment link sent to %s.") % self.email,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Email Sent"),
                "message": _("Payment link sent to %s.") % self.email,
                "type": "success",
                "sticky": False,
            },
        }
