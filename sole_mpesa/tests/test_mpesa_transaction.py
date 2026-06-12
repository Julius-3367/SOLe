# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestMpesaTransaction(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.config = cls.env["sole.mpesa.config"].create({
            "name": "Test Config",
            "environment": "sandbox",
            "consumer_key": "test_key",
            "consumer_secret": "test_secret",
            "shortcode": "174379",
            "passkey": "test_passkey",
            "callback_url_base": "https://example.com",
            "is_active": True,
        })
        cls.partner = cls.env["res.partner"].create({"name": "M-Pesa Test Customer"})

    def _create_tx(self, **kwargs):
        vals = {
            "config_id": self.config.id,
            "transaction_type": "stk_push",
            "phone": "254712345678",
            "amount": 1000.0,
            "account_ref": "INV/TEST/0001",
            "checkout_request_id": "ws_CO_test_123",
            "merchant_request_id": "mr_test_123",
            "state": "pending",
        }
        vals.update(kwargs)
        return self.env["sole.mpesa.transaction"].create(vals)

    # ── action_create_journal_entry ───────────────────────────────────────────
    def test_create_journal_entry_requires_journal(self):
        self.config.account_journal_id = False
        tx = self._create_tx(state="completed")
        with self.assertRaises(UserError):
            tx.action_create_journal_entry()

    def test_create_journal_entry_creates_and_reconciles_payment(self):
        self.config.account_journal_id = self.bank_journal

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "ref": "INV/TEST/0001",
            "invoice_line_ids": [(0, 0, {
                "name": "Test product",
                "quantity": 1,
                "price_unit": 1000.0,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.payment_state, "not_paid")

        tx = self._create_tx(
            state="completed",
            partner_id=self.partner.id,
            mpesa_receipt_number="QGR12345XY",
            result_code="0",
            result_desc="The service request is processed successfully.",
        )
        tx.action_create_journal_entry()

        self.assertTrue(tx.move_id)
        self.assertEqual(tx.move_id.state, "posted")
        invoice.invalidate_recordset()
        self.assertEqual(invoice.payment_state, "paid")

    def test_create_journal_entry_is_idempotent(self):
        self.config.account_journal_id = self.bank_journal
        tx = self._create_tx(state="completed")
        tx.action_create_journal_entry()
        first_move = tx.move_id
        # Calling again on an already-posted transaction must not create a
        # second payment — it should just return the existing one.
        tx.action_create_journal_entry()
        self.assertEqual(tx.move_id, first_move)

    def test_create_journal_entry_rejects_non_completed(self):
        tx = self._create_tx(state="pending")
        with self.assertRaises(UserError):
            tx.action_create_journal_entry()

    # ── action_check_status ────────────────────────────────────────────────────
    def test_check_status_marks_completed_on_result_code_zero(self):
        tx = self._create_tx(state="pending")
        with patch.object(
            type(self.config), "action_query_stk_status",
            return_value={"ResultCode": 0, "ResultDesc": "The service request is processed successfully."},
        ):
            tx.action_check_status()
        self.assertEqual(tx.state, "completed")
        self.assertEqual(tx.result_code, "0")

    def test_check_status_marks_cancelled_on_1032(self):
        tx = self._create_tx(state="pending")
        with patch.object(
            type(self.config), "action_query_stk_status",
            return_value={"ResultCode": 1032, "ResultDesc": "Request cancelled by user"},
        ):
            tx.action_check_status()
        self.assertEqual(tx.state, "cancelled")

    def test_check_status_marks_failed_on_other_code(self):
        tx = self._create_tx(state="pending")
        with patch.object(
            type(self.config), "action_query_stk_status",
            return_value={"ResultCode": 1, "ResultDesc": "Insufficient balance"},
        ):
            tx.action_check_status()
        self.assertEqual(tx.state, "failed")

    def test_check_status_leaves_pending_while_still_processing(self):
        tx = self._create_tx(state="pending")
        # Daraja returns no top-level ResultCode while the transaction is
        # still being processed (it returns an errorCode instead).
        with patch.object(
            type(self.config), "action_query_stk_status",
            return_value={"errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"},
        ):
            tx.action_check_status()
        self.assertEqual(tx.state, "pending")

    def test_check_status_ignores_c2b_and_non_pending(self):
        c2b_tx = self._create_tx(transaction_type="c2b", state="completed")
        with patch.object(type(self.config), "action_query_stk_status") as mocked:
            c2b_tx.action_check_status()
        mocked.assert_not_called()

    # ── _cron_auto_reconcile ────────────────────────────────────────────────────
    def test_cron_auto_reconcile_completes_pending_and_posts_payment(self):
        self.config.account_journal_id = self.bank_journal
        tx = self._create_tx(state="pending", partner_id=self.partner.id)

        with patch.object(
            type(self.config), "action_query_stk_status",
            return_value={"ResultCode": 0, "ResultDesc": "The service request is processed successfully."},
        ):
            self.env["sole.mpesa.transaction"]._cron_auto_reconcile()

        self.assertEqual(tx.state, "completed")
        self.assertTrue(tx.move_id)
        self.assertEqual(tx.move_id.state, "posted")

    def test_cron_auto_reconcile_posts_already_completed_c2b_without_move(self):
        self.config.account_journal_id = self.bank_journal
        tx = self._create_tx(
            transaction_type="c2b",
            state="completed",
            result_code="0",
            result_desc="Received",
        )

        self.env["sole.mpesa.transaction"]._cron_auto_reconcile()

        self.assertTrue(tx.move_id)
        self.assertEqual(tx.move_id.state, "posted")

    def test_cron_auto_reconcile_skips_completed_without_journal_configured(self):
        self.config.account_journal_id = False
        tx = self._create_tx(state="completed", result_code="0")

        # Must not raise even though no payment journal is configured.
        self.env["sole.mpesa.transaction"]._cron_auto_reconcile()

        self.assertFalse(tx.move_id)
