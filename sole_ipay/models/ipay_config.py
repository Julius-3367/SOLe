# -*- coding: utf-8 -*-
"""
sole.ipay.config — iPay Kenya payment gateway configuration.

iPay payment URL signature algorithm (SHA256 HMAC):
  hash = HMAC-SHA256(key=hash_key, data=live+oid+inv+ttl+tel+eml+vid+curr+p1+p2+p3+p4+cbk+cst+crl)
"""
import hashlib
import hmac
import logging
import urllib.parse

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

IPAY_LIVE_URL = "https://www.ipay.co.ke/pay"
IPAY_SANDBOX_URL = "https://sandbox.ipay.co.ke/pay"


class SoleIpayConfig(models.Model):
    _name = "sole.ipay.config"
    _description = "iPay Payment Gateway Configuration"
    _rec_name = "name"

    name = fields.Char(string="Config Name", required=True, default="iPay Config")
    environment = fields.Selection(
        [("sandbox", "Sandbox"), ("live", "Live")],
        string="Environment",
        required=True,
        default="sandbox",
    )
    vendor_id = fields.Char(
        string="Vendor ID (vid)",
        required=True,
        help="Your iPay merchant vendor ID.",
    )
    hash_key = fields.Char(
        string="Hash Key",
        required=True,
        help="Secret hash key provided by iPay for signature generation.",
    )
    callback_url = fields.Char(
        string="Callback URL (cbk)",
        required=True,
        help="URL iPay will POST payment confirmation to, e.g. https://sole.co.ke/sole/ipay/callback",
        default="https://sole.co.ke/sole/ipay/callback",
    )
    currency = fields.Char(
        string="Currency Code",
        default="KES",
        required=True,
    )
    is_active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    account_journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        domain=[("type", "=", "bank")],
    )
    transaction_count = fields.Integer(
        string="Transactions",
        compute="_compute_transaction_count",
    )

    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = self.env["sole.ipay.transaction"].search_count(
                [("config_id", "=", rec.id)]
            )

    @property
    def _payment_url(self):
        return IPAY_LIVE_URL if self.environment == "live" else IPAY_SANDBOX_URL

    def _generate_hash(self, live, oid, inv, ttl, tel, eml, p1="", p2="", p3="", p4="", cst="1", crl="0"):
        """Generate HMAC-SHA256 hash for iPay payment parameters."""
        data = "".join([live, oid, inv, ttl, tel, eml, self.vendor_id,
                        self.currency, p1, p2, p3, p4, self.callback_url, cst, crl])
        signature = hmac.new(
            self.hash_key.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def generate_payment_url(self, order_id, invoice_no, amount, phone, email,
                             p1="", p2="", p3="", p4=""):
        """Build a signed iPay payment URL.

        Returns (payment_url: str, hash: str)
        """
        self.ensure_one()
        live = "1" if self.environment == "live" else "0"
        ttl = f"{amount:.2f}"
        phone_clean = phone.strip().replace(" ", "").replace("-", "")
        signature = self._generate_hash(
            live=live, oid=order_id, inv=invoice_no,
            ttl=ttl, tel=phone_clean, eml=email,
            p1=p1, p2=p2, p3=p3, p4=p4,
        )
        params = {
            "live": live,
            "oid": order_id,
            "inv": invoice_no,
            "ttl": ttl,
            "tel": phone_clean,
            "eml": email,
            "vid": self.vendor_id,
            "curr": self.currency,
            "p1": p1, "p2": p2, "p3": p3, "p4": p4,
            "cbk": self.callback_url,
            "cst": "1",
            "crl": "0",
            "hsh": signature,
        }
        return f"{self._payment_url}?{urllib.parse.urlencode(params)}", signature

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("iPay Transactions"),
            "res_model": "sole.ipay.transaction",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
        }
