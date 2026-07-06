# -*- coding: utf-8 -*-
"""DLR (Delivery Receipt) webhook — POST /sole/sms/dlr"""
import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SoleSmsDlrController(http.Controller):

    @http.route("/sole/sms/dlr", type="http", auth="public", csrf=False, methods=["POST", "GET"])
    def dlr_callback(self, **kwargs):
        _logger.info("SMS DLR received: %s", kwargs)

        # Reject requests that don't carry a valid token.
        incoming_token = kwargs.get("token", "")
        if not self._token_valid(incoming_token):
            _logger.warning("SMS DLR rejected: invalid or missing token")
            return request.make_response("Forbidden", status=403)

        msg_id = kwargs.get("messageId", kwargs.get("id", ""))
        status = kwargs.get("status", kwargs.get("deliveryStatus", "")).lower()
        if msg_id:
            log = (
                request.env["sole.sms.log"]
                .sudo()
                .search([("provider_msg_id", "=", str(msg_id))], limit=1)
            )
            if log:
                new_state = "delivered" if "deliver" in status else "failed"
                log.sudo().write({"state": new_state})
        return request.make_response("OK", status=200)

    @staticmethod
    def _token_valid(incoming_token):
        """Return True if incoming_token matches any active provider's dlr_token."""
        if not incoming_token:
            return False
        providers = (
            request.env["sole.sms.provider"]
            .sudo()
            .search([("is_active", "=", True), ("dlr_token", "!=", False)])
        )
        for provider in providers:
            # constant-time compare to prevent timing attacks
            if hmac.compare_digest(str(provider.dlr_token), str(incoming_token)):
                return True
        return False
