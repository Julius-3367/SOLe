# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.exceptions import UserError
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestAsset(AccountingKitCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.asset_category = cls.env['account.asset.category'].create({
            'name': 'Test Equipment',
            'type': 'purchase',
            'price': 0.0,
            'account_asset_id': cls.account_asset_fixed.id,
            'account_depreciation_id': cls.account_asset_fixed.id,
            'account_depreciation_expense_id': cls.account_depreciation_exp.id,
            'journal_id': cls.journal_general.id,
            'method': 'linear',
            'method_number': 5,
            'method_period': 12,
        })

    def test_asset_category_currency_is_company_currency(self):
        """Asset category must default to company currency, not USD — Kenya fix."""
        new_cat = self.env['account.asset.category'].create({
            'name': 'Currency Check',
            'type': 'purchase',
            'price': 0.0,
            'account_asset_id': self.account_asset_fixed.id,
            'account_depreciation_id': self.account_asset_fixed.id,
            'account_depreciation_expense_id': self.account_depreciation_exp.id,
            'journal_id': self.journal_general.id,
            'method': 'linear',
            'method_number': 3,
            'method_period': 12,
        })
        self.assertEqual(
            new_cat.currency_id.id, self.company.currency_id.id,
            "Asset category currency must default to company currency",
        )
        self.assertNotEqual(
            new_cat.currency_id.name, 'USD',
            "Asset category must NOT default to USD for a KES company",
        )

    def test_asset_create_and_depreciation_board(self):
        """Create an asset — depreciation board auto-computes on create."""
        asset = self.env['account.asset.asset'].create({
            'name': 'Office Laptop',
            'category_id': self.asset_category.id,
            'value': 120000.0,
            'date': '2025-01-01',
        })
        self.assertEqual(asset.state, 'draft')
        self.assertTrue(
            asset.depreciation_line_ids,
            "Depreciation board must be generated on asset creation",
        )
        # Linear 5-year: 5 annual entries
        self.assertEqual(len(asset.depreciation_line_ids), 5)
        for line in asset.depreciation_line_ids:
            self.assertAlmostEqual(line.amount, 24000.0, places=2)

    def test_asset_validate_state_and_currency(self):
        """Validate an asset — state goes open, currency remains KES."""
        asset = self.env['account.asset.asset'].create({
            'name': 'Motor Vehicle',
            'category_id': self.asset_category.id,
            'value': 1500000.0,
            'date': '2025-01-01',
        })
        asset.validate()
        self.assertEqual(asset.state, 'open')
        self.assertEqual(
            asset.currency_id.id, self.company.currency_id.id,
            "Asset currency must match company currency after validation",
        )

    def test_asset_residual_equals_gross_before_posting(self):
        """Residual value equals gross value before any depreciation is posted."""
        asset = self.env['account.asset.asset'].create({
            'name': 'Plant',
            'category_id': self.asset_category.id,
            'value': 500000.0,
            'date': '2025-01-01',
        })
        self.assertAlmostEqual(asset.value_residual, 500000.0, places=2)

    def test_cannot_delete_open_asset(self):
        """Deleting an open asset must raise UserError."""
        asset = self.env['account.asset.asset'].create({
            'name': 'Locked Asset',
            'category_id': self.asset_category.id,
            'value': 10000.0,
            'date': '2025-01-01',
        })
        asset.validate()
        with self.assertRaises(UserError):
            asset.unlink()

    def test_set_to_draft_reverts_state(self):
        """set_to_draft must revert a validated asset back to draft."""
        asset = self.env['account.asset.asset'].create({
            'name': 'Draftable Asset',
            'category_id': self.asset_category.id,
            'value': 30000.0,
            'date': '2025-01-01',
        })
        asset.validate()
        self.assertEqual(asset.state, 'open')
        asset.set_to_draft()
        self.assertEqual(asset.state, 'draft')
