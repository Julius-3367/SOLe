# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.exceptions import UserError
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestCreditLimit(AccountingKitCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'customer_credit_limit', True)
        cls.journal_sale = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)],
            limit=1,
        )
        cls.account_income = cls.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)

    def _make_partner(self, warning=5000.0, blocking=10000.0):
        return self.env['res.partner'].create({
            'name': 'Credit Test Partner',
            'customer_rank': 1,
            'active_limit': True,
            'warning_stage': warning,
            'blocking_stage': blocking,
        })

    def _post_invoice(self, partner, amount):
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Sale',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.account_income.id,
            })],
        })
        inv.action_post()
        return inv

    def test_warning_constraint_raises_when_warning_gte_blocking(self):
        """Warning stage must be less than blocking stage when limit is active."""
        with self.assertRaises(UserError):
            self.env['res.partner'].create({
                'name': 'Bad Limit Partner',
                'customer_rank': 1,
                'active_limit': True,
                'warning_stage': 10000.0,
                'blocking_stage': 5000.0,
            })

    def test_credit_limit_enabled_reflects_config(self):
        """enable_credit_limit field mirrors the system config parameter."""
        partner = self._make_partner()
        self.assertTrue(partner.enable_credit_limit)

        self.env['ir.config_parameter'].sudo().set_param(
            'customer_credit_limit', False)
        partner._compute_enable_credit_limit()
        self.assertFalse(partner.enable_credit_limit)

        # Restore
        self.env['ir.config_parameter'].sudo().set_param(
            'customer_credit_limit', True)

    def test_blocking_prevents_second_invoice_post(self):
        """After first invoice pushes due_amount above blocking_stage, second post is blocked."""
        # blocking_stage = 500: first invoice (1000) posts OK (due_amount was 0)
        # second invoice post must fail (due_amount now 1000 > 500)
        partner = self._make_partner(warning=0, blocking=500.0)

        # First invoice succeeds — partner credit is 0 before posting
        self._post_invoice(partner, 1000.0)

        # Force ORM cache flush so due_amount reflects the new receivable
        partner.invalidate_recordset()

        # Second invoice should be blocked
        inv2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Blocked Sale',
                'quantity': 1,
                'price_unit': 100.0,
                'account_id': self.account_income.id,
            })],
        })
        with self.assertRaises(UserError):
            inv2.action_post()

    def test_no_blocking_when_limit_inactive(self):
        """Partner with active_limit=False is never blocked regardless of due_amount."""
        partner = self.env['res.partner'].create({
            'name': 'Unlim Partner',
            'customer_rank': 1,
            'active_limit': False,
            'blocking_stage': 1.0,
        })
        # Post a large invoice — should not raise
        self._post_invoice(partner, 99999.0)
        partner.invalidate_recordset()
        inv2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Unlimited Sale',
                'quantity': 1,
                'price_unit': 50000.0,
                'account_id': self.account_income.id,
            })],
        })
        # Should NOT raise
        inv2.action_post()
        self.assertEqual(inv2.state, 'posted')
