# -*- coding: utf-8 -*-
"""
sole.mpesa.config — Safaricom Daraja API configuration and token management.
"""
import base64
import logging
from datetime import datetime, timedelta

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PROD_BASE = "https://api.safaricom.co.ke"


class SoleMpesaConfig(models.Model):
    _name = "sole.mpesa.config"
    _description = "M-Pesa Daraja API Configuration"
    _rec_name = "name"

    name = fields.Char(string="Config Name", required=True, default="M-Pesa Config")
    environment = fields.Selection(
        [("sandbox", "Sandbox"), ("production", "Production")],
        string="Environment",
        required=True,
        default="sandbox",
    )
    consumer_key = fields.Char(string="Consumer Key", required=True)
    consumer_secret = fields.Char(string="Consumer Secret", required=True)
    shortcode = fields.Char(
        string="Business Short Code",
        required=True,
        help="Your Paybill or Till number.",
    )
    passkey = fields.Char(
        string="Lipa Na M-Pesa Passkey",
        help="Provided by Safaricom for STK Push.",
    )
    c2b_shortcode = fields.Char(
        string="C2B Short Code",
        help="Short code for C2B Paybill (if different from STK short code).",
    )
    callback_url_base = fields.Char(
        string="Callback Base URL",
        required=True,
        help="Public base URL of this Odoo instance, e.g. https://sole.co.ke",
        default="https://sole.co.ke",
    )
    account_journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        help="Journal used to record confirmed M-Pesa payments.",
        domain=[("type", "=", "bank")],
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    is_active = fields.Boolean(string="Active", default=True)

    # ── Token cache (stored, not computed) ────────────────────────────────────
    _access_token = fields.Char(store=False)  # not stored — use ICP
    token_expiry = fields.Datetime(string="Token Expiry", readonly=True)

    # ── Computed ──────────────────────────────────────────────────────────────
    transaction_count = fields.Integer(
        string="Transactions",
        compute="_compute_transaction_count",
    )
    stk_callback_url = fields.Char(
        string="STK Callback URL",
        compute="_compute_callback_urls",
        help="Register this URL with Safaricom for STK Push callbacks.",
    )
    c2b_validation_url = fields.Char(
        string="C2B Validation URL",
        compute="_compute_callback_urls",
    )
    c2b_confirmation_url = fields.Char(
        string="C2B Confirmation URL",
        compute="_compute_callback_urls",
    )

    def _compute_callback_urls(self):
        for rec in self:
            base = (rec.callback_url_base or "").rstrip("/")
            rec.stk_callback_url = f"{base}/sole/mpesa/stk/callback" if base else ""
            rec.c2b_validation_url = f"{base}/sole/mpesa/c2b/validation" if base else ""
            rec.c2b_confirmation_url = f"{base}/sole/mpesa/c2b/confirmation" if base else ""

    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = self.env["sole.mpesa.transaction"].search_count(
                [("config_id", "=", rec.id)]
            )

    @property
    def _base_url(self):
        return PROD_BASE if self.environment == "production" else SANDBOX_BASE

    # ── Access Token ──────────────────────────────────────────────────────────
    def _get_access_token(self):
        """Return a valid OAuth2 access token, fetching a new one if expired."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        param_key = f"sole_mpesa.token.{self.id}"
        expiry_key = f"sole_mpesa.token_expiry.{self.id}"
        token = icp.get_param(param_key, "")
        expiry_str = icp.get_param(expiry_key, "")
        if token and expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str)
                if datetime.utcnow() < expiry - timedelta(seconds=60):
                    return token
            except (ValueError, TypeError):
                pass
        # Fetch new token
        credentials = base64.b64encode(
            f"{self.consumer_key}:{self.consumer_secret}".encode()
        ).decode()
        try:
            resp = requests.get(
                f"{self._base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {credentials}"},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("M-Pesa token request failed: %s") % exc) from exc
        data = resp.json()
        token = data.get("access_token", "")
        expires_in = int(data.get("expires_in", 3600))
        expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        icp.set_param(param_key, token)
        icp.set_param(expiry_key, expiry.isoformat())
        _logger.info("M-Pesa: fetched new access token (expires %s)", expiry)
        return token

    # ── STK Push ─────────────────────────────────────────────────────────────
    def action_stk_push(self, phone, amount, account_ref, transaction_desc="Payment"):
        """Initiate an STK Push payment request.

        Returns the raw Daraja JSON response dict.
        """
        self.ensure_one()
        if not self.passkey:
            raise UserError(_("Lipa Na M-Pesa Passkey is required for STK Push."))
        token = self._get_access_token()
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode()
        ).decode()
        callback_url = f"{self.callback_url_base.rstrip('/')}/sole/mpesa/stk/callback"
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": self._normalize_phone(phone),
            "PartyB": self.shortcode,
            "PhoneNumber": self._normalize_phone(phone),
            "CallBackURL": callback_url,
            "AccountReference": account_ref[:12],
            "TransactionDesc": transaction_desc[:13],
        }
        try:
            resp = requests.post(
                f"{self._base_url}/mpesa/stkpush/v1/processrequest",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("STK Push failed: %s") % exc) from exc
        return resp.json()

    # ── STK Push Query ───────────────────────────────────────────────────────
    def action_query_stk_status(self, checkout_request_id):
        """Query the result of a previously-initiated STK Push.

        Returns the raw Daraja JSON response dict (includes ResultCode /
        ResultDesc once the customer has responded to the prompt).
        """
        self.ensure_one()
        if not self.passkey:
            raise UserError(_("Lipa Na M-Pesa Passkey is required for STK Push."))
        token = self._get_access_token()
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.shortcode}{self.passkey}{timestamp}".encode()
        ).decode()
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }
        try:
            resp = requests.post(
                f"{self._base_url}/mpesa/stkpushquery/v1/query",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("STK Push status query failed: %s") % exc) from exc
        return resp.json()

    # ── C2B URL Registration ──────────────────────────────────────────────────
    def action_register_c2b_urls(self):
        """Register C2B validation and confirmation URLs with Safaricom."""
        self.ensure_one()
        token = self._get_access_token()
        base = self.callback_url_base.rstrip("/")
        payload = {
            "ShortCode": self.c2b_shortcode or self.shortcode,
            "ResponseType": "Completed",
            "ConfirmationURL": f"{base}/sole/mpesa/c2b/confirmation",
            "ValidationURL": f"{base}/sole/mpesa/c2b/validation",
        }
        try:
            resp = requests.post(
                f"{self._base_url}/mpesa/c2b/v1/registerurl",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("C2B URL registration failed: %s") % exc) from exc
        result = resp.json()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("C2B URLs Registered"),
                "message": str(result.get("ResponseDescription", result)),
                "type": "success",
            },
        }

    def action_test_token(self):
        """Test API credentials by fetching a token."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(f"sole_mpesa.token.{self.id}", "")  # force refresh
        token = self._get_access_token()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Token OK"),
                "message": _("Successfully obtained access token: ...%s") % token[-8:],
                "type": "success",
            },
        }

    @staticmethod
    def _normalize_phone(phone):
        """Normalize a Kenyan phone number to 254XXXXXXXXX format."""
        phone = str(phone).strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        if not phone.startswith("254"):
            phone = "254" + phone
        return phone

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("M-Pesa Transactions"),
            "res_model": "sole.mpesa.transaction",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
        }
