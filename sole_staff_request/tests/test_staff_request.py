# -*- coding: utf-8 -*-
from datetime import date

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStaffRequest(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the accounting test base runs as an accountant; HR and settings data needs more
        cls.su = cls.env(su=True)
        company = cls.su.company
        cls.cash = cls.company_data["default_journal_cash"]
        cls.expense_account = cls.company_data["default_account_expense"]
        cls.advance_account = cls.su["account.account"].create({
            "name": "Staff Advances", "code": "145099", "account_type": "asset_current",
        })
        company.write({
            "sole_staff_advance_account_id": cls.advance_account.id,
            "sole_request_journal_id": cls.cash.id,
        })

        cls.requester = new_test_user(cls.su, login="sr_requester", groups="base.group_user")
        cls.manager = new_test_user(cls.su, login="sr_manager", groups="base.group_user")
        cls.colleague = new_test_user(cls.su, login="sr_colleague", groups="base.group_user")
        cls.finance = new_test_user(
            cls.su, login="sr_finance",
            groups="base.group_user,sole_staff_request.group_staff_request_finance")
        company.sole_request_finance_user_id = cls.finance

        Employee = cls.su["hr.employee"]
        cls.manager_emp = Employee.create({"name": "Manager", "user_id": cls.manager.id})
        cls.requester_emp = Employee.create({
            "name": "Requester", "user_id": cls.requester.id, "parent_id": cls.manager_emp.id,
        })
        Employee.create({"name": "Colleague", "user_id": cls.colleague.id})

        cls.transport = cls.su.ref("sole_staff_request.type_transport")
        cls.transport.expense_account_id = cls.expense_account
        cls.advance_type = cls.su.ref("sole_staff_request.type_salary_advance")

    def _new_request(self, type_=None, amount=1500):
        return self.env["sole.staff.request"].with_user(self.requester).create({
            "type_id": (type_ or self.transport).id,
            "amount": amount,
            "purpose": "Fare to Kiwool Advocates, Upper Hill, mail server install",
        })

    def _pay(self, request, **kw):
        wizard = self.env["sole.staff.request.pay"].with_user(self.finance).create({
            "request_id": request.id, "reference": "SJK4XB2Q7M", **kw,
        })
        wizard.action_pay()

    def test_submit_approve_pay_posts_entry(self):
        request = self._new_request()
        self.assertEqual(request.employee_id, self.requester_emp)
        self.assertTrue(request.name.startswith("SR/"))

        request.action_submit()
        self.assertEqual(request.state, "submitted")
        self.assertEqual(request.approver_id, self.manager)
        self.assertTrue(request.activity_ids.filtered(lambda a: a.user_id == self.manager))

        with self.assertRaises(UserError):
            request.action_approve()                       # requester cannot approve their own

        request.with_user(self.manager).action_approve()
        self.assertEqual(request.state, "approved")
        self.assertTrue(request.activity_ids.filtered(lambda a: a.user_id == self.finance))

        self._pay(request)
        self.assertEqual(request.state, "paid")
        move = request.sudo().move_id
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.journal_id, self.cash)
        debit = move.line_ids.filtered(lambda l: l.debit)
        credit = move.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(debit.account_id, self.expense_account)
        self.assertEqual(debit.debit, 1500)
        self.assertEqual(credit.account_id, self.cash.default_account_id)
        self.assertEqual(debit.partner_id, self.requester_emp.work_contact_id)
        self.assertEqual(request.payment_reference, "SJK4XB2Q7M")
        self.assertEqual(request.paid_by_id, self.finance)

    def test_reject_needs_reason(self):
        request = self._new_request()
        request.action_submit()
        wizard = self.env["sole.staff.request.reject"].with_user(self.manager)
        with self.assertRaises(UserError):
            wizard.create({"request_id": request.id, "reason": "   "}).action_reject()
        wizard.create({"request_id": request.id, "reason": "Use the company car"}).action_reject()
        self.assertEqual(request.state, "rejected")
        self.assertEqual(request.rejection_reason, "Use the company car")

        request.with_user(self.requester).action_reset_draft()
        self.assertEqual(request.state, "draft")

    def test_requester_cannot_shortcut_the_workflow(self):
        request = self._new_request()
        with self.assertRaises(UserError):
            request.with_user(self.requester).write({"state": "approved"})
        request.action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.requester).write({"amount": 9000})
        with self.assertRaises(UserError):
            request.with_user(self.manager).action_open_pay_wizard()    # managers approve, finance pays

    def test_other_staff_cannot_see_the_request(self):
        request = self._new_request()
        with self.assertRaises(AccessError):
            request.with_user(self.colleague).read(["amount"])
        self.assertEqual(request.with_user(self.finance).amount, 1500)

    def test_type_limit(self):
        self.transport.max_amount = 1000
        request = self._new_request(amount=1500)
        with self.assertRaises(UserError):
            request.action_submit()

    def test_no_manager_uses_default_approver(self):
        self.requester_emp.parent_id = False
        request = self._new_request()
        with self.assertRaises(UserError):
            request.action_submit()                        # nobody to approve yet
        self.su.company.sole_request_default_approver_id = self.manager
        request.action_submit()
        self.assertEqual(request.approver_id, self.manager)

    def test_salary_advance_recovered_through_payroll(self):
        structure = self.su.ref("sole_payroll_ke.structure_ke")
        self.assertIn("STAFF_ADVANCE", structure.rule_ids.mapped("code"))
        version = self.requester_emp.version_id
        version.write({"wage": 50000, "contract_date_start": date(2026, 1, 1), "struct_id": structure.id})

        request = self._new_request(type_=self.advance_type, amount=5000)
        self.assertTrue(request.recover_via_payroll)
        request.action_submit()
        request.with_user(self.manager).action_approve()
        self._pay(request, recovery_date=date(2026, 10, 1))

        debit = request.sudo().move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit.account_id, self.advance_account)
        self.assertEqual(request.recovery_status, "pending")

        def payslip(month):
            slip = self.su["hr.payslip"].create({
                "name": "Payslip", "employee_id": self.requester_emp.id, "contract_id": version.id,
                "struct_id": structure.id,
                "date_from": date(2026, month, 1),
                "date_to": date(2026, month, 30 if month in (9, 11) else 31),
            })
            slip.action_compute_sheet()
            return slip, {l.code: l.total for l in slip.line_ids}

        _sept, lines = payslip(9)
        self.assertNotIn("STAFF_ADVANCE", lines)           # recovery starts in October

        october, lines = payslip(10)
        self.assertEqual(lines["STAFF_ADVANCE"], 5000)
        october.action_payslip_done()
        self.assertEqual(request.recovered_payslip_id, october)
        self.assertEqual(request.recovery_status, "done")

        _nov, lines = payslip(11)
        self.assertNotIn("STAFF_ADVANCE", lines)           # recovered once only

        october.action_payslip_cancel()
        self.assertEqual(request.recovery_status, "pending")
