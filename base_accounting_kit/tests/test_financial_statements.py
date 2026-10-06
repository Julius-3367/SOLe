# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import tagged
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestFinancialStatements(AccountingKitCommon):
    """Profit and Loss and Balance Sheet figures for a small 2026 ledger:
    a 50,000 sale, a 10,000 expense and 6,000 of depreciation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_income = cls.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)
        cls.account_accumulated = cls.env['account.account'].create({
            'name': 'Accumulated Depreciation (test)',
            'code': '199902',
            'account_type': 'asset_non_current',
        })
        cls._entry('2026-03-31', cls.account_receivable, cls.account_income, 50000)
        cls._entry('2026-04-30', cls.account_expense, cls.account_payable, 10000)
        cls._entry('2026-12-31', cls.account_depreciation_exp, cls.account_accumulated, 6000)

    @classmethod
    def _entry(cls, date, debit_account, credit_account, amount):
        cls.env['account.move'].create({
            'date': date,
            'journal_id': cls.journal_general.id,
            'line_ids': [
                Command.create({'account_id': debit_account.id, 'balance': amount}),
                Command.create({'account_id': credit_account.id, 'balance': -amount}),
            ],
        }).action_post()

    def _balances(self, report_xmlid):
        report = self.env.ref(report_xmlid)
        period = {'date_from': '2026-01-01', 'date_to': '2026-12-31'}
        wizard = self.env['financial.report'].create({
            'account_report_id': report.id, 'target_move': 'posted',
            'debit_credit': False, 'enable_filter': False, **period,
        })
        lines = wizard.get_account_lines({
            'account_report_id': [report.id, report.name],
            'target_move': 'posted', 'debit_credit': False, 'enable_filter': False,
            'used_context': {**period, 'state': 'posted', 'strict_range': True},
            **period,
        })
        return {line['name']: line['balance'] for line in lines if line['type'] == 'report'}

    def test_profit_and_loss_includes_depreciation(self):
        pnl = self._balances('base_accounting_kit.account_financial_report_profitandloss0')
        # This report shows costs as negative figures; depreciation follows suit.
        self.assertAlmostEqual(pnl['Expense'], -10000.0, places=2)
        self.assertAlmostEqual(pnl['Depreciation'], -6000.0, places=2)
        self.assertAlmostEqual(pnl['Profit and Loss'], 34000.0, places=2)

    def test_balance_sheet_balances_once_depreciation_is_posted(self):
        bs = self._balances('base_accounting_kit.account_financial_report_balancesheet0')
        self.assertAlmostEqual(bs['Assets'], 44000.0, places=2)
        self.assertAlmostEqual(bs['Current Year Earnings'], -34000.0, places=2)
        liabilities = self.env.ref('base_accounting_kit.account_financial_report_liabilitysum0').name
        self.assertAlmostEqual(
            bs['Assets'] + bs[liabilities] + bs['Equity'], 0.0, places=2,
            msg="assets must equal liabilities plus equity")
