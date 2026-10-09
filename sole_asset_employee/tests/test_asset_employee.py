# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestAssetEmployee(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Employees are HR's to create; the test user keeps the books.
        HR = cls.env(su=True)
        cls.department = HR['hr.department'].create({'name': 'Support'})
        cls.wanjiru = HR['hr.employee'].create({'name': 'Wanjiru Kamau', 'department_id': cls.department.id})
        cls.otieno = HR['hr.employee'].create({'name': 'Otieno Ouma'})
        fixtures = cls.env['account.account'].create({
            'name': 'Fixtures and fittings', 'code': '150100', 'account_type': 'asset_fixed',
        })
        cls.category = cls.env['account.asset.category'].create({
            'name': 'Fixtures and fitting', 'type': 'purchase', 'price': 20000,
            'journal_id': cls.company_data['default_journal_misc'].id,
            'account_asset_id': fixtures.id, 'account_depreciation_id': fixtures.id,
            'account_depreciation_expense_id': cls.company_data['default_account_expense'].id,
            'method_number': 5, 'method_period': 12,
        })

    def _asset(self, name, employee=None):
        return self.env['account.asset.asset'].create({
            'name': name, 'category_id': self.category.id, 'value': 20000,
            'date': '2026-01-30', 'employee_id': employee.id if employee else False,
        })

    def test_an_asset_has_an_assigned_employee_and_their_department(self):
        table = self._asset('Conference table', self.wanjiru)
        self.assertEqual(table.employee_id, self.wanjiru)
        self.assertEqual(table.department_id, self.department)

    def test_reassigning_is_recorded_in_the_chatter(self):
        # The accounting test base turns tracking off; it is the point here.
        tracked = {k: v for k, v in self.env.context.items() if k not in ('tracking_disable', 'mail_notrack')}
        table = self._asset('Conference table', self.wanjiru).with_context(tracked, tracking_disable=False)
        self.env.flush_all()
        self.env.cr.precommit.run()   # Odoo posts tracking when the transaction commits
        table.employee_id = self.otieno
        self.env.flush_all()
        self.env.cr.precommit.run()
        changes = table.message_ids.tracking_value_ids.filtered(lambda t: t.field_id.name == 'employee_id')
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes.old_value_char, 'Wanjiru Kamau')
        self.assertEqual(changes.new_value_char, 'Otieno Ouma')

    def test_an_employee_lists_the_assets_they_hold(self):
        laptop = self._asset('Laptop', self.wanjiru)
        table = self._asset('Conference table', self.wanjiru)
        self._asset('Printer', self.otieno)
        self.assertEqual(self.wanjiru.asset_count, 2)
        action = self.wanjiru.action_view_assets()
        self.assertEqual(self.env['account.asset.asset'].search(action['domain']), laptop | table)

    def test_assets_group_by_employee(self):
        self._asset('Laptop', self.wanjiru)
        self._asset('Desk', self.wanjiru)
        self._asset('Spare chair')
        groups = dict(self.env['account.asset.asset']._read_group(
            [('category_id', '=', self.category.id)], ['employee_id'], ['__count']))
        self.assertEqual(groups[self.wanjiru], 2)
        self.assertEqual(groups[self.env['hr.employee']], 1)
