# -*- coding: utf-8 -*-
"""
M-Pesa Daraja webhook controllers:
  POST /sole/mpesa/stk/callback      — STK Push result callback
  POST /sole/mpesa/c2b/validation    — C2B validation URL
  POST /sole/mpesa/c2b/confirmation  — C2B confirmation URL
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SoleMpesaController(http.Controller):

    # ── STK Push callback ─────────────────────────────────────────────────────
    @http.route("/sole/mpesa/stk/callback", type="json", auth="public", csrf=False)
    def stk_callback(self, **kwargs):
        try:
            body = request.get_json_data()
        except Exception:
            body = {}
        _logger.info("M-Pesa STK callback: %s", json.dumps(body))
        try:
            stk_body = body.get("Body", {}).get("stkCallback", {})
            checkout_id = stk_body.get("CheckoutRequestID", "")
            result_code = str(stk_body.get("ResultCode", "-1"))
            result_desc = stk_body.get("ResultDesc", "")
            tx = request.env["sole.mpesa.transaction"].sudo().search(
                [("checkout_request_id", "=", checkout_id)], limit=1
            )
            if tx:
                vals = {
                    "result_code": result_code,
                    "result_desc": result_desc,
                    "raw_payload": json.dumps(body),
                    "state": "completed" if result_code == "0" else "failed",
                }
                if result_code == "0":
                    items = (
                        stk_body.get("CallbackMetadata", {}).get("Item", [])
                    )
                    meta = {i["Name"]: i.get("Value") for i in items}
                    vals["mpesa_receipt_number"] = str(meta.get("MpesaReceiptNumber", ""))
                    vals["mpesa_transaction_date"] = str(meta.get("TransactionDate", ""))
                    vals["amount"] = float(meta.get("Amount", tx.amount))
                    vals["phone"] = str(meta.get("PhoneNumber", tx.phone))
                tx.sudo().write(vals)
        except Exception as exc:
            _logger.exception("M-Pesa STK callback processing error: %s", exc)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── C2B Validation ────────────────────────────────────────────────────────
    @http.route("/sole/mpesa/c2b/validation", type="json", auth="public", csrf=False)
    def c2b_validation(self, **kwargs):
        try:
            body = request.get_json_data()
        except Exception:
            body = {}
        _logger.info("M-Pesa C2B validation: %s", json.dumps(body))
        # Accept all by default; add custom rejection logic here
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── C2B Confirmation ──────────────────────────────────────────────────────
    @http.route("/sole/mpesa/c2b/confirmation", type="json", auth="public", csrf=False)
    def c2b_confirmation(self, **kwargs):
        try:
            body = request.get_json_data()
        except Exception:
            body = {}
        _logger.info("M-Pesa C2B confirmation: %s", json.dumps(body))
        try:
            config = (
                request.env["sole.mpesa.config"]
                .sudo()
                .search([("is_active", "=", True)], limit=1)
            )
            request.env["sole.mpesa.transaction"].sudo().create({
                "config_id": config.id if config else False,
                "transaction_type": "c2b",
                "phone": str(body.get("MSISDN", "")),
                "amount": float(body.get("TransactionAmount", 0)),
                "account_ref": str(body.get("BillRefNumber", "")),
                "mpesa_receipt_number": str(body.get("TransID", "")),
                "mpesa_transaction_date": str(body.get("TransTime", "")),
                "merchant_request_id": str(body.get("TransID", "")),
                "checkout_request_id": str(body.get("TransID", "")),
                "result_code": "0",
                "result_desc": "Received",
                "state": "completed",
                "raw_payload": json.dumps(body),
            })
        except Exception as exc:
            _logger.exception("M-Pesa C2B confirmation processing error: %s", exc)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
