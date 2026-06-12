# -*- coding: utf-8 -*-
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestSmsProviderSandbox(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sandbox_provider = cls.env["sole.sms.provider"].create({
            "name": "Sandbox Provider",
            "provider_type": "onfon",
            "api_url": "https://api.onfonmedia.co.ke/v1/sms/SendBulkSMS",
            "sender_id": "SOLe",
            "test_mode": True,
        })
        cls.live_provider = cls.env["sole.sms.provider"].create({
            "name": "Live Provider (no creds)",
            "provider_type": "generic_http",
            # Port 9 ("discard") is reliably closed/refused locally, so this
            # fails fast without depending on outbound network access.
            "api_url": "http://127.0.0.1:9/sms",
            "sender_id": "SOLe",
            "timeout_s": 2,
            "test_mode": False,
        })

    def test_test_mode_does_not_call_external_api(self):
        success, msg_id, error = self.sandbox_provider.send_sms("0712345678", "Hello")

        self.assertTrue(success)
        self.assertTrue(msg_id.startswith("SANDBOX-"))
        self.assertFalse(error)

    def test_test_mode_normalizes_phone_in_log(self):
        # _normalize_phone is applied before the sandbox responds; make sure
        # send_sms doesn't error out on a raw local-format number.
        success, msg_id, _error = self.sandbox_provider.send_sms("0712 345-678", "Hello")
        self.assertTrue(success)
        self.assertTrue(msg_id)

    def test_non_test_mode_attempts_real_request_and_fails_cleanly(self):
        # No real endpoint to hit; the generic HTTP path must fail gracefully
        # (network error) rather than raising, when test_mode is off.
        success, msg_id, error = self.live_provider.send_sms("0712345678", "Hello")

        self.assertFalse(success)
        self.assertEqual(msg_id, "")
        self.assertTrue(error)
