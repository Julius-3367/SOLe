# -*- coding: utf-8 -*-
from odoo.tests import tagged
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestAssetPosting(AccountingKitCommon):
    """Posting depreciation lines to the ledger, by every route the UI offers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_accumulated = cls.env['account.account'].create({
            'name': 'Accumulated Depreciation (test)',
            'code': '199901',
            'account_type': 'asset_non_current',
        })
        cls.category = cls.env['account.asset.category'].create({
            'name': 'Vehicles',
            'type': 'purchase',
            'price': 0.0,
            'account_asset_id': cls.account_asset_fixed.id,
            'account_depreciation_id': cls.account_accumulated.id,
            'account_depreciation_expense_id': cls.account_depreciation_exp.id,
            'journal_id': cls.journal_general.id,
            'method': 'linear',
            'method_number': 5,
            'method_period': 12,
            'open_asset': True,
        })

    def _running_asset(self, **vals):
        asset = self.env['account.asset.asset'].create({
            'name': 'Delivery Van',
            'category_id': self.category.id,
            'value': 120000.0,
            'date': '2025-01-01',
            **vals,
        })
        asset.validate()
        return asset

    def _first_line(self, asset):
        return asset.depreciation_line_ids.sorted('depreciation_date')[0]

    def _split(self, move):
        expense = move.line_ids.filtered(
            lambda l: l.account_id == self.account_depreciation_exp)
        return expense, move.line_ids - expense

    def test_posting_a_line_books_a_balanced_depreciation_entry(self):
        asset = self._running_asset()
        line = self._first_line(asset)

        line.create_move()

        move = line.move_id
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.date, line.depreciation_date)
        expense, accumulated = self._split(move)
        self.assertAlmostEqual(expense.debit, 24000.0, places=2)
        self.assertAlmostEqual(accumulated.credit, 24000.0, places=2)
        self.assertEqual(accumulated.account_id, self.account_accumulated)
        self.assertTrue(line.move_check)
        self.assertTrue(line.move_posted_check)

    def test_posting_reduces_the_residual_value(self):
        asset = self._running_asset()
        self._first_line(asset).create_move()
        self.assertAlmostEqual(asset.value_residual, 96000.0, places=2)

    def test_entry_stays_draft_when_the_category_does_not_auto_confirm(self):
        self.category.open_asset = False
        asset = self._running_asset()
        line = self._first_line(asset)

        line.create_move()

        self.assertEqual(line.move_id.state, 'draft')

    def test_foreign_currency_asset_is_booked_in_company_currency(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        # 1 KES = 0.01 USD, so 1 USD = 100 KES.
        self.env['res.currency.rate'].create({
            'currency_id': usd.id,
            'name': '2024-01-01',
            'rate': 0.01,
            'company_id': self.company.id,
        })
        asset = self._running_asset(currency_id=usd.id, value=1200.0)
        line = self._first_line(asset)

        line.create_move()

        expense, accumulated = self._split(line.move_id)
        self.assertAlmostEqual(expense.debit, 24000.0, places=2)
        self.assertAlmostEqual(expense.amount_currency, 240.0, places=2)
        self.assertEqual(expense.currency_id, usd)
        self.assertAlmostEqual(accumulated.amount_currency, -240.0, places=2)

    def test_grouped_category_posts_one_entry_for_all_its_assets(self):
        self.category.group_entries = True
        van = self._running_asset()
        truck = self._running_asset(name='Truck', value=60000.0)
        lines = self._first_line(van) | self._first_line(truck)

        lines.create_grouped_move()

        move = lines.mapped('move_id')
        self.assertEqual(len(move), 1)
        self.assertEqual(move.state, 'posted')
        expense, accumulated = self._split(move)
        self.assertAlmostEqual(expense.debit, 36000.0, places=2)
        self.assertAlmostEqual(accumulated.credit, 36000.0, places=2)

    def test_generate_entries_wizard_posts_everything_due(self):
        van = self._running_asset()
        wizard = self.env['asset.depreciation.confirmation.wizard'].create({
            'date': '2025-12-31',
        })

        wizard.asset_compute()

        line = self._first_line(van)
        self.assertTrue(line.move_id)
        self.assertEqual(line.move_id.state, 'posted')
