# -*- coding: utf-8 -*-
"""
iPay callback controller — POST /sole/ipay/callback
iPay posts form-encoded data with payment result.
"""
import hashlib
import hmac
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SoleIpayController(http.Controller):

    @http.route("/sole/ipay/callback", type="http", auth="public", csrf=False, methods=["POST"])
    def ipay_callback(self, **post):
        _logger.info("iPay callback received: %s", post)
        status = post.get("status", "")
        oid = post.get("oid", "")
        txn_ref = post.get("txncd", post.get("id_mpesa", ""))
        mc = post.get("mc", "")           # amount paid by customer
        p1 = post.get("p1", "")
        p2 = post.get("p2", "")
        p3 = post.get("p3", "")
        p4 = post.get("p4", "")

        # Retrieve config to validate hash
        config = (
            request.env["sole.ipay.config"]
            .sudo()
            .search([("is_active", "=", True)], limit=1)
        )

        # Validate hash if config found
        if config and "hsh" in post:
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

        # Find matching transaction
        tx = (
            request.env["sole.ipay.transaction"]
            .sudo()
            .search([("order_id", "=", oid)], limit=1)
        )

        new_state = "paid" if status in ("aei7p7yrx4ae34", "00", "success") else "failed"
        if tx:
            tx.sudo().write({
                "ipay_status": status,
                "ipay_txn_ref": txn_ref,
                "state": new_state,
                "raw_callback": str(post),
                "amount": float(mc) if mc else tx.amount,
            })
        else:
            # Create a new transaction record from callback data
            if config:
                request.env["sole.ipay.transaction"].sudo().create({
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

        return request.make_response("OK", status=200)
