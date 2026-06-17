# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo.tests import tagged
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestRecurringPayments(AccountingKitCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_credit = cls.env['account.account'].search(
            [('account_type', '=', 'liability_current')], limit=1)

    def test_recurring_entry_created_by_cron(self):
        """Cron must create a journal entry for a running recurring payment."""
        start_date = date.today() - timedelta(days=35)
        template = self.env['account.recurring.payments'].create({
            'name': 'Monthly Rent',
            'debit_account': self.account_expense.id,
            'credit_account': self.account_credit.id,
            'journal_id': self.journal_general.id,
            'date': start_date,
            'recurring_period': 'months',
            'recurring_interval': 1,
            'amount': 50000.0,
            'pay_time': 'pay_later',
            'journal_state': 'draft',
            'state': 'running',
        })
        moves_before = self.env['account.move'].search_count(
            [('recurring_ref', '!=', False)])
        self.env['account.recurring.payments']._cron_generate_entries()
        moves_after = self.env['account.move'].search_count(
            [('recurring_ref', '!=', False)])
        self.assertGreater(
            moves_after, moves_before,
            "Cron should have created at least one new journal entry",
        )
        # Verify the entry belongs to the correct accounts
        new_move = self.env['account.move'].search(
            [('recurring_ref', 'like', str(template.id) + '/')],
            order='id desc', limit=1)
        self.assertTrue(new_move, "A journal entry with the template ref must exist")
        account_ids = new_move.line_ids.mapped('account_id.id')
        self.assertIn(self.account_expense.id, account_ids)
        self.assertIn(self.account_credit.id, account_ids)

    def test_draft_template_not_processed(self):
        """Draft recurring payment templates must be ignored by the cron."""
        start_date = date.today() - timedelta(days=5)
        self.env['account.recurring.payments'].create({
            'name': 'Draft Subscription',
            'debit_account': self.account_expense.id,
            'credit_account': self.account_credit.id,
            'journal_id': self.journal_general.id,
            'date': start_date,
            'recurring_period': 'months',
            'recurring_interval': 1,
            'amount': 1000.0,
            'pay_time': 'pay_later',
            'journal_state': 'draft',
            'state': 'draft',
        })
        moves_before = self.env['account.move'].search_count(
            [('recurring_ref', '!=', False)])
        self.env['account.recurring.payments']._cron_generate_entries()
        moves_after = self.env['account.move'].search_count(
            [('recurring_ref', '!=', False)])
        self.assertEqual(
            moves_before, moves_after,
            "Draft templates must produce no journal entries",
        )

    def test_idempotent_cron(self):
        """Running cron twice must not duplicate journal entries."""
        start_date = date.today() - timedelta(days=10)
        self.env['account.recurring.payments'].create({
            'name': 'Weekly Wage',
            'debit_account': self.account_expense.id,
            'credit_account': self.account_credit.id,
            'journal_id': self.journal_general.id,
            'date': start_date,
            'recurring_period': 'weeks',
            'recurring_interval': 1,
            'amount': 20000.0,
            'pay_time': 'pay_later',
            'journal_state': 'draft',
            'state': 'running',
        })
        self.env['account.recurring.payments']._cron_generate_entries()
        count_first = self.env['account.move'].search_count(
            [('recurring_ref', '!=', False)])
        self.env['account.recurring.payments']._cron_generate_entries()
        count_second = self.env['account.move'].search_count(
            [('recurring_ref', '!=', False)])
        self.assertEqual(
            count_first, count_second,
            "Running cron twice must not create duplicate entries",
        )
