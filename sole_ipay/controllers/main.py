# -*- coding: utf-8 -*-
"""
iPay callback controller — POST /sole/ipay/callback

iPay posts form-encoded data after a payment attempt. This endpoint:
1. Finds the active iPay config and validates the HMAC hash.
2. Locates the matching transaction by order ID.
3. Updates state to paid/failed.
4. On success, auto-reconciles the linked invoice.
"""
import hashlib
import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# iPay success status codes
IPAY_SUCCESS_STATUSES = {"aei7p7yrx4ae34", "00", "success"}


class SoleIpayController(http.Controller):

    @http.route("/sole/ipay/callback", type="http", auth="public", csrf=False, methods=["POST"])
    def ipay_callback(self, **post):
        _logger.info("iPay callback received for order=%s status=%s",
                     post.get("oid"), post.get("status"))

        oid = post.get("oid", "").strip()
        status = post.get("status", "").strip()
        txn_ref = post.get("txncd", post.get("id_mpesa", "")).strip()
        mc = post.get("mc", "")
        p1 = post.get("p1", "")
        p2 = post.get("p2", "")
        p3 = post.get("p3", "")
        p4 = post.get("p4", "")

        if not oid:
            _logger.warning("iPay callback: missing order ID")
            return request.make_response("Missing order ID", status=400)

        config = (
            request.env["sole.ipay.config"]
            .sudo()
            .search([("is_active", "=", True)], limit=1)
        )

        # Reject if no config: we cannot validate the hash
        if not config:
            _logger.error("iPay callback: no active config found — cannot validate")
            return request.make_response("No active config", status=500)

        # Always validate the hash — reject mismatches
        if "hsh" not in post:
            _logger.warning("iPay callback: missing hash for order %s", oid)
            return request.make_response("Missing hash", status=400)

        expected = config._generate_hash(
            live=post.get("live", "0"),
            oid=oid,
            inv=post.get("inv", ""),
            ttl=post.get("ttl", ""),
            tel=post.get("tel", ""),
            eml=post.get("eml", ""),
            p1=p1, p2=p2, p3=p3, p4=p4,
            cst=post.get("cst", "1"),
            crl=post.get("crl", "0"),
        )
        if not hmac.compare_digest(expected, post.get("hsh", "")):
            _logger.warning("iPay callback: hash mismatch for order %s", oid)
            return request.make_response("Invalid signature", status=400)

        # Find the transaction
        tx = (
            request.env["sole.ipay.transaction"]
            .sudo()
            .search([("order_id", "=", oid)], limit=1)
        )

        is_paid = status in IPAY_SUCCESS_STATUSES
        new_state = "paid" if is_paid else "failed"

        if tx:
            # Guard against double-processing a paid transaction
            if tx.state == "paid":
                _logger.info("iPay callback: order %s already paid — ignoring duplicate", oid)
                return request.make_response("OK", status=200)

            amount = float(mc) if mc else tx.amount
            tx.sudo().write({
                "ipay_status": status,
                "ipay_txn_ref": txn_ref,
                "state": new_state,
                "raw_callback": str(post),
                "amount": amount,
            })
            if is_paid:
                try:
                    tx.sudo()._reconcile_invoice()
                except Exception:
                    _logger.exception(
                        "iPay callback: invoice reconciliation failed for order %s", oid
                    )
        else:
            # No prior transaction — create one from callback data
            tx = request.env["sole.ipay.transaction"].sudo().create({
                "config_id": config.id,
                "order_id": oid,
                "invoice_no": post.get("inv", oid),
                "amount": float(mc) if mc else 0.0,
                "phone": post.get("tel", ""),
                "email": post.get("eml", ""),
                "ipay_status": status,
                "ipay_txn_ref": txn_ref,
                "state": new_state,
                "raw_callback": str(post),
                "p1": p1, "p2": p2, "p3": p3, "p4": p4,
            })
            _logger.info("iPay callback: created transaction for unknown order %s", oid)

        return request.make_response("OK", status=200)
