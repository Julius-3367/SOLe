# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class AccountingKitCommon(TransactionCase):
    """Shared setup for base_accounting_kit tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Odoo ships KES inactive, so look past the active filter
        cls.currency_kes = cls.env['res.currency'].with_context(
            active_test=False).search([('name', '=', 'KES')], limit=1)
        if cls.currency_kes:
            cls.currency_kes.active = True
        else:
            cls.currency_kes = cls.env['res.currency'].create({
                'name': 'KES', 'symbol': 'KSh', 'rounding': 0.01,
            })

        # Ensure company uses KES
        cls.company.write({'currency_id': cls.currency_kes.id})

        # Journals
        cls.journal_general = cls.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', cls.company.id)],
            limit=1)

        # Accounts by type
        def _account(atype):
            return cls.env['account.account'].search(
                [('account_type', '=', atype)], limit=1)

        cls.account_asset_fixed = _account('asset_fixed')
        cls.account_depreciation_exp = _account('expense_depreciation')
        cls.account_expense = _account('expense')
        cls.account_receivable = _account('asset_receivable')
        cls.account_payable = _account('liability_payable')
