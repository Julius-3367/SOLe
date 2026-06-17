# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo.tests import tagged
from odoo import fields
from odoo.exceptions import UserError
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestFollowup(AccountingKitCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal_sale = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)],
            limit=1,
        )
        cls.account_income = cls.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)

        # Ensure follow-up config exists
        followup = cls.env['account.followup'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        if not followup:
            followup = cls.env['account.followup'].create(
                {'company_id': cls.company.id})
        if not followup.followup_line_ids:
            cls.env['followup.line'].create({
                'name': 'First Reminder',
                'delay': 5,
                'followup_id': followup.id,
            })

        cls.customer = cls.env['res.partner'].create({
            'name': 'Test Customer KE',
            'customer_rank': 1,
            'email': 'test@example.co.ke',
        })

    def _make_invoice(self, partner, days_overdue, amount=10000.0):
        due_date = date.today() - timedelta(days=days_overdue)
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': due_date,
            'invoice_date_due': due_date,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Service',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.account_income.id,
            })],
        })
        inv.action_post()
        return inv

    def test_no_invoices_no_action_needed(self):
        """Partner with no invoices must have no_action_needed status."""
        partner = self.env['res.partner'].create({
            'name': 'Clean Partner', 'customer_rank': 1,
        })
        partner._compute_for_followup()
        self.assertEqual(partner.followup_status, 'no_action_needed')

    def test_overdue_invoice_triggers_followup_status(self):
        """Partner with a 30-day overdue invoice must show a followup status."""
        self._make_invoice(self.customer, days_overdue=30)
        self.customer.invalidate_recordset()
        self.customer._compute_for_followup()
        self.assertIn(
            self.customer.followup_status,
            ('in_need_of_action', 'with_overdue_invoices'),
        )
        self.assertGreater(self.customer.total_overdue, 0)

    def test_total_due_accumulates(self):
        """total_due must sum all unpaid invoice residuals."""
        partner = self.env['res.partner'].create({
            'name': 'Multi-Invoice Partner',
            'customer_rank': 1,
            'email': 'multi@example.co.ke',
        })
        self._make_invoice(partner, days_overdue=10, amount=5000.0)
        self._make_invoice(partner, days_overdue=20, amount=3000.0)
        partner.invalidate_recordset()
        partner._compute_for_followup()
        self.assertAlmostEqual(partner.total_due, 8000.0, places=2)

    def test_send_followup_email_without_email_raises(self):
        """Sending follow-up to partner with no email must raise UserError."""
        partner = self.env['res.partner'].create({
            'name': 'No Email Partner', 'customer_rank': 1,
        })
        with self.assertRaises(UserError):
            partner.action_send_followup_email()

    def test_cron_skips_recently_reminded(self):
        """Cron must not re-send if last reminder was today."""
        self._make_invoice(self.customer, days_overdue=30)
        self.customer.invalidate_recordset()
        self.customer._compute_for_followup()
        # Mark as reminded today
        self.customer.followup_reminder_sent = fields.Date.today()
        self.env['res.partner']._cron_send_followup_reminders()
        # Date should not have changed to None or a future date
        self.assertEqual(self.customer.followup_reminder_sent, fields.Date.today())
