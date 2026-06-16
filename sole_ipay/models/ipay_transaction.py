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
        string="iPay Config",
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
    ipay_status = fields.Char(string="iPay Status Code")
    ipay_txn_ref = fields.Char(string="iPay Txn Reference", index=True)
    raw_callback = fields.Text(string="Raw Callback")
    partner_id = fields.Many2one("res.partner", string="Customer")
    # invoice_id: the source invoice this payment request was raised from
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        readonly=True,
        ondelete="set null",
        index=True,
    )
    # move_id: the Odoo payment journal entry created after reconciliation
    move_id = fields.Many2one("account.move", string="Payment Entry", readonly=True)
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

    # ── Core logic (callable from both buttons and automated flows) ───────────

    def _do_generate_url(self):
        """Build and store the signed payment URL. Raises UserError on bad input."""
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
        _logger.info("iPay URL generated for order %s", self.order_id)

    def _do_send_url_email(self):
        """Email the payment link to the customer. Raises UserError if preconditions unmet."""
        self.ensure_one()
        if not self.payment_url:
            raise UserError(_("Generate the payment URL before sending it."))
        if not self.email:
            raise UserError(_("A customer email address is required."))
        customer_name = self.partner_id.name if self.partner_id else _("Customer")
        self.env["mail.mail"].sudo().create({
            "subject": _("Payment Request — %s") % self.order_id,
            "body_html": _(
                "<p>Dear %(name)s,</p>"
                "<p>Please complete your payment of "
                "<strong>%(currency)s %(amount).2f</strong>:</p>"
                "<p style='margin:16px 0;'>"
                "<a href='%(url)s' style='background:#017e84;color:#fff;"
                "padding:12px 24px;text-decoration:none;border-radius:4px;"
                "display:inline-block;font-weight:bold;'>Pay Now</a></p>"
                "<p>Or copy this link:<br/>"
                "<code style='word-break:break-all;'>%(url)s</code></p>"
                "<p>Reference: <strong>%(order)s</strong></p>"
            ) % {
                "name": customer_name,
                "currency": self.config_id.currency,
                "amount": self.amount,
                "url": self.payment_url,
                "order": self.order_id,
            },
            "email_to": self.email,
            "email_from": self.env.company.email or self.env.user.email,
        }).send()
        self.message_post(
            body=_("Payment link emailed to %s.") % self.email,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def _reconcile_invoice(self):
        """Register an Odoo payment against the linked invoice and reconcile it.

        Called automatically from the iPay callback when status is paid.
        Does nothing if no invoice is linked, journal is not configured,
        or the invoice is already fully paid.
        """
        self.ensure_one()
        invoice = self.invoice_id
        journal = self.config_id.account_journal_id
        if not invoice or not journal:
            return
        if invoice.state != "posted":
            _logger.warning("iPay reconcile: invoice %s is not posted", invoice.name)
            return
        if invoice.payment_state == "paid":
            _logger.info("iPay reconcile: invoice %s already paid", invoice.name)
            return

        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": (self.partner_id or invoice.partner_id).id,
            "amount": self.amount,
            "journal_id": journal.id,
            "ref": self.ipay_txn_ref or self.order_id,
            "date": fields.Date.today(),
            "currency_id": invoice.currency_id.id,
        })
        payment.action_post()

        # Reconcile payment receivable line against invoice receivable line
        pay_line = payment.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
        )
        inv_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled
        )
        if pay_line and inv_line:
            (pay_line + inv_line).reconcile()
            self.write({"move_id": payment.move_id.id})
            self.message_post(
                body=_("Invoice %s reconciled via iPay payment %s.")
                % (invoice.name, self.ipay_txn_ref or self.order_id),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            _logger.info(
                "iPay: reconciled invoice %s with payment %s",
                invoice.name,
                payment.name,
            )
        else:
            _logger.warning(
                "iPay: could not find receivable lines to reconcile for invoice %s",
                invoice.name,
            )

    # ── Web button actions ────────────────────────────────────────────────────

    def action_generate_url(self):
        """Generate the signed URL and reload the form so it is immediately visible."""
        self.ensure_one()
        self._do_generate_url()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Payment URL Ready"),
                "message": _(
                    "The payment link has been generated. "
                    "Copy it from the banner below or click 'Send URL to Customer'."
                ),
                "type": "success",
                "sticky": True,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": self._name,
                    "res_id": self.id,
                    "view_mode": "form",
                    "views": [(False, "form")],
                    "target": "current",
                },
            },
        }

    def action_open_payment_url(self):
        """Open the iPay payment page in a new browser tab."""
        self.ensure_one()
        if not self.payment_url:
            raise UserError(_("Generate the payment URL first."))
        return {"type": "ir.actions.act_url", "url": self.payment_url, "target": "new"}

    def action_send_url_email(self):
        """Email the payment link to the customer and show a confirmation toast."""
        self.ensure_one()
        self._do_send_url_email()
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
