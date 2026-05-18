# -*- coding: utf-8 -*-
"""
sole.sms.provider — SMS gateway configuration and send engine.

Supports Onfon Media (primary) and a generic HTTP adapter.
"""
import json
import logging
import re

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ONFON_SEND_URL = "https://api.onfonmedia.co.ke/v1/sms/SendBulkSMS"


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

    log_count = fields.Integer(string="Logs", compute="_compute_log_count")

    def _compute_log_count(self):
        for rec in self:
            rec.log_count = self.env["sole.sms.log"].search_count(
                [("provider_id", "=", rec.id)]
            )

    # ── Send ────────────────────────────────────────────────────────────────
    def send_sms(self, phone, message):
        """Send a single SMS. Returns (success: bool, provider_msg_id: str, error: str)."""
        self.ensure_one()
        phone = self._normalize_phone(phone)
        if self.provider_type == "onfon":
            return self._send_onfon(phone, message)
        return self._send_generic(phone, message)

    def _send_onfon(self, phone, message):
        """Send via OnfonMedia BulkSMS API."""
        payload = {
            "SenderId": self.sender_id,
            "MessageParameters": [{"Number": phone, "Text": message}],
            "ApiKey": self.api_key,
            "ClientId": self.username or "",
        }
        try:
            resp = requests.post(
                ONFON_SEND_URL,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
            # Onfon returns Data[0].MessageId on success
            msg_id = ""
            if isinstance(data.get("Data"), list) and data["Data"]:
                msg_id = str(data["Data"][0].get("MessageId", ""))
            code = data.get("ErrorCode", "")
            if str(code) not in ("", "0", "100", "101", "200"):
                return False, msg_id, data.get("ErrorDescription", str(data))
            return True, msg_id, ""
        except requests.RequestException as exc:
            return False, "", str(exc)

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
