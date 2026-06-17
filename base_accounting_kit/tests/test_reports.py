# -*- coding: utf-8 -*-
from odoo.tests import tagged
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestReports(AccountingKitCommon):
    """Smoke-test report wizards: instantiate and compute without errors."""

    def test_financial_report_wizard(self):
        """Financial report wizard must create with a valid account report."""
        report = self.env['account.financial.report'].search([], limit=1)
        self.assertTrue(report, "Need at least one account.financial.report record")
        wizard = self.env['financial.report'].create({
            'account_report_id': report.id,
            'target_move': 'posted',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
        })
        self.assertTrue(wizard.id)

    def test_aged_partner_wizard(self):
        """Aged partner balance wizard must instantiate without errors."""
        wizard = self.env['account.aged.trial.balance'].create({
            'result_selection': 'customer',
            'period_length': 30,
            'date_from': '2025-12-31',
        })
        self.assertTrue(wizard.id)

    def test_trial_balance_wizard(self):
        """Trial balance wizard must instantiate without errors."""
        wizard = self.env['account.balance.report'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
        })
        self.assertTrue(wizard.id)

    def test_general_ledger_wizard(self):
        """General ledger wizard must instantiate without errors."""
        wizard = self.env['account.report.general.ledger'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
            'sortby': 'sort_date',
        })
        self.assertTrue(wizard.id)

    def test_partner_ledger_wizard(self):
        """Partner ledger wizard must instantiate without errors."""
        wizard = self.env['account.report.partner.ledger'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
            'result_selection': 'customer',
        })
        self.assertTrue(wizard.id)

    def test_cash_flow_wizard(self):
        """Cash flow wizard must instantiate without errors."""
        report = self.env['account.financial.report'].search([], limit=1)
        wizard = self.env['cash.flow.report'].create({
            'account_report_id': report.id,
            'target_move': 'posted',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
        })
        self.assertTrue(wizard.id)

    def test_bank_book_wizard(self):
        """Bank book wizard must instantiate — uses journal_ids Many2many."""
        wizard = self.env['account.bank.book.report'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
        })
        self.assertTrue(wizard.id)

    def test_cash_book_wizard(self):
        """Cash book wizard must instantiate — uses journal_ids Many2many."""
        wizard = self.env['account.cash.book.report'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
        })
        self.assertTrue(wizard.id)

    def test_day_book_wizard(self):
        """Day book wizard must instantiate without errors."""
        wizard = self.env['account.day.book.report'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
        })
        self.assertTrue(wizard.id)

    def test_tax_report_wizard(self):
        """Tax report wizard must instantiate without errors."""
        wizard = self.env['kit.account.tax.report'].create({
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'target_move': 'posted',
        })
        self.assertTrue(wizard.id)

    def test_get_account_lines_returns_list(self):
        """get_account_lines must return a non-crashing list for any report."""
        report = self.env['account.financial.report'].search([], limit=1)
        wizard = self.env['financial.report'].create({
            'account_report_id': report.id,
            'target_move': 'posted',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'debit_credit': True,
            'enable_filter': False,
        })
        form_data = {
            'account_report_id': [report.id, report.name],
            'target_move': 'posted',
            'date_from': '2025-01-01',
            'date_to': '2025-12-31',
            'debit_credit': True,
            'enable_filter': False,
            'used_context': {
                'date_from': '2025-01-01',
                'date_to': '2025-12-31',
                'state': 'posted',
                'strict_range': True,
                'lang': 'en_US',
            },
        }
        lines = wizard.get_account_lines(form_data)
        self.assertIsInstance(lines, list)
