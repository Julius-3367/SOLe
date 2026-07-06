# -*- coding: utf-8 -*-
"""
sole.sms.provider — SMS gateway configuration and send engine.

Supports Onfon Media (primary) and a generic HTTP adapter.
"""
import json
import logging
import re
import secrets
import uuid

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ONFON_SEND_URL = "https://api.onfonmedia.co.ke/v1/sms/SendBulkSMS"
ONFON_BULK_SIZE = 100  # max recipients per single Onfon API call


class SoleSmsProvider(models.Model):
    _name = "sole.sms.provider"
    _description = "SMS Provider / Gateway"
    _rec_name = "name"

    name = fields.Char(string="Provider Name", required=True)
    provider_type = fields.Selection(
        [("onfon", "OnfonMedia"), ("generic_http", "Generic HTTP")],
        string="Provider Type",
        required=True,
        default="onfon",
    )
    api_url = fields.Char(string="API Endpoint URL", required=True)
    api_key = fields.Char(string="API Key")
    username = fields.Char(string="Username")
    sender_id = fields.Char(string="Sender ID", required=True)
    is_active = fields.Boolean(string="Active", default=True)
    test_mode = fields.Boolean(
        string="Test Mode",
        default=False,
        help="When enabled, no SMS is actually sent. Each message is recorded "
             "as sent with a simulated provider message ID, so campaigns, "
             "recipients and logs can be exercised end-to-end without "
             "credentials or live credit.",
    )
    timeout_s = fields.Integer(string="Timeout (s)", default=30)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # Generic HTTP extra config
    auth_header_name = fields.Char(string="Auth Header Name", default="apiKey")
    extra_params = fields.Text(string="Extra Params (JSON)", help='e.g. {"Type": 1}')

    dlr_token = fields.Char(
        string="DLR Webhook Token",
        copy=False,
        help="Secret token appended to the DLR callback URL (?token=…). "
             "Onfon must be configured to send this token so forged callbacks are rejected.",
    )
    dlr_url = fields.Char(string="DLR Callback URL", compute="_compute_dlr_url", store=False)

    def _compute_dlr_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            if rec.dlr_token:
                rec.dlr_url = "%s/sole/sms/dlr?token=%s" % (base, rec.dlr_token)
            else:
                rec.dlr_url = "%s/sole/sms/dlr  (generate a token first)" % base

    def action_generate_dlr_token(self):
        self.ensure_one()
        self.dlr_token = secrets.token_urlsafe(32)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Token Generated"), "message": _("DLR token refreshed. Update your Onfon callback URL."), "type": "success"},
        }

    log_count = fields.Integer(string="Logs", compute="_compute_log_count")

    def _compute_log_count(self):
        for rec in self:
            rec.log_count = self.env["sole.sms.log"].search_count(
                [("provider_id", "=", rec.id)]
            )

    # ── Send ────────────────────────────────────────────────────────────────
    def send_sms(self, phone, message):
        """Send a single SMS. Returns (success, provider_msg_id, error)."""
        self.ensure_one()
        phone = self._normalize_phone(phone)
        if self.test_mode:
            return self._send_sandbox(phone, message)
        if self.provider_type == "onfon":
            return self._send_onfon(phone, message)
        return self._send_generic(phone, message)

    def send_sms_bulk(self, recipients):
        """Send to multiple recipients efficiently.

        Args:
            recipients: list of (phone, message) tuples (phones already normalised)

        Returns:
            list of (success, provider_msg_id, error) in the same order.
        """
        self.ensure_one()
        if not recipients:
            return []
        if self.test_mode:
            return [self._send_sandbox(phone, msg) for phone, msg in recipients]
        if self.provider_type == "onfon":
            return self._send_onfon_bulk(recipients)
        # Generic HTTP has no multi-recipient spec — fall back to serial sends.
        return [self._send_generic(phone, msg) for phone, msg in recipients]

    def _send_sandbox(self, phone, message):
        """Simulate a successful send without calling any external API."""
        msg_id = "SANDBOX-%s" % uuid.uuid4().hex[:12]
        _logger.info("[sole_sms][test_mode] %s → %s (%s)", self.name, phone, msg_id)
        return True, msg_id, ""

    def _send_onfon(self, phone, message):
        """Send a single message via OnfonMedia BulkSMS API."""
        results = self._send_onfon_bulk([(phone, message)])
        return results[0]

    def _send_onfon_bulk(self, recipients):
        """Send up to ONFON_BULK_SIZE recipients per API call.

        Onfon's MessageParameters array accepts multiple entries, each with its
        own Number and Text, so one HTTP round-trip handles 100 recipients.
        1 000 recipients = 10 API calls instead of 1 000.
        """
        url = self.api_url or ONFON_SEND_URL
        results = []
        # Chunk into groups of ONFON_BULK_SIZE
        for i in range(0, len(recipients), ONFON_BULK_SIZE):
            chunk = recipients[i: i + ONFON_BULK_SIZE]
            payload = {
                "SenderId": self.sender_id,
                "ApiKey": self.api_key,
                "ClientId": self.username or "",
                "MessageParameters": [
                    {"Number": phone, "Text": msg} for phone, msg in chunk
                ],
            }
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=self.timeout_s,
                )
                resp.raise_for_status()
                data = resp.json()
                top_code = str(data.get("ErrorCode", ""))
                top_error = data.get("ErrorDescription", "")
                items = data.get("Data") if isinstance(data.get("Data"), list) else []

                for idx, (phone, _msg) in enumerate(chunk):
                    item = items[idx] if idx < len(items) else {}
                    msg_id = str(item.get("MessageId", ""))
                    if top_code not in ("", "0", "100", "101", "200"):
                        results.append((False, msg_id, top_error or str(data)))
                        continue
                    item_code = str(item.get("MessageErrorCode", "0"))
                    if item_code not in ("", "0"):
                        results.append((False, msg_id, item.get("MessageErrorDescription", str(data))))
                    else:
                        results.append((True, msg_id, ""))

            except requests.RequestException as exc:
                error = str(exc)
                results.extend([(False, "", error)] * len(chunk))

        return results

    def _send_generic(self, phone, message):
        """Send via generic HTTP POST."""
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.auth_header_name:
            headers[self.auth_header_name] = self.api_key
        payload = {"to": phone, "message": message, "from": self.sender_id}
        if self.extra_params:
            try:
                payload.update(json.loads(self.extra_params))
            except (json.JSONDecodeError, ValueError):
                pass
        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            return True, "", ""
        except requests.RequestException as exc:
            return False, "", str(exc)

    @staticmethod
    def _normalize_phone(phone):
        phone = re.sub(r"[\s\-()]", "", str(phone))
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0") and len(phone) == 10:
            phone = "254" + phone[1:]
        elif not phone.startswith("254"):
            phone = "254" + phone
        return phone

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("SMS Logs"),
            "res_model": "sole.sms.log",
            "view_mode": "list,form",
            "domain": [("provider_id", "=", self.id)],
        }
