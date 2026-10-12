# -*- coding: utf-8 -*-
"""October 2026 payslips checked against figures worked by hand.

Rates in force: NSSF 6% on 9,000 / 108,000 (from Feb 2026), SHIF 2.75%,
AHL 1.5% of gross, PAYE bands 10/25/30%, personal relief 2,400, SHIF and AHL
deductible from taxable pay.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestKenyanPayslip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structure = cls.env.ref("sole_payroll_ke.structure_ke")
        cls.employee = cls.env["hr.employee"].create({"name": "Wanjiku Test"})
        cls.version = cls.employee.version_id
        cls.version.write({
            "wage": 100000,
            "contract_date_start": date(2026, 1, 1),
            "struct_id": cls.structure.id,
        })

    def _compute(self, inputs=None):
        slip = self.env["hr.payslip"].create({
            "name": "October 2026",
            "employee_id": self.employee.id,
            "contract_id": self.version.id,
            "struct_id": self.structure.id,
            "date_from": date(2026, 10, 1),
            "date_to": date(2026, 10, 31),
        })
        for code, amount in (inputs or {}).items():
            self.env["hr.payslip.input"].create({
                "name": code, "code": code, "amount": amount,
                "payslip_id": slip.id, "contract_id": self.version.id,
                "date_from": slip.date_from, "date_to": slip.date_to,
            })
        slip.action_compute_sheet()
        return {line.code: line.total for line in slip.line_ids}

    def test_basic_salary_only(self):
        t = self._compute()
        self.assertAlmostEqual(t["GROSS"], 100000)
        self.assertAlmostEqual(t["NSSF_AMOUNT"], 6000)       # 540 + 5,460
        self.assertAlmostEqual(t["SHIF_AMOUNT"], 2750)
        self.assertAlmostEqual(t["AHL_AMOUNT"], 1500)
        self.assertAlmostEqual(t["GROSS_TAXABLE"], 89750)
        self.assertAlmostEqual(t["PAYE"], 19308.35, places=2)
        self.assertAlmostEqual(t["NET"], 70441.65, places=2)
        self.assertNotIn("HELB", t)
        self.assertNotIn("FIXED_DED", t)
        self.assertNotIn("BONUS", t)

    def test_helb_fixed_lines_and_taxable_allowance(self):
        self.version.ke_helb = 2000
        self.env["sole.payroll.recurring.line"].create([
            {"version_id": self.version.id, "name": "SACCO", "kind": "deduction",
             "amount": 1000, "date_from": date(2026, 1, 1)},
            {"version_id": self.version.id, "name": "Old loan, finished", "kind": "deduction",
             "amount": 3000, "date_from": date(2026, 1, 1), "date_to": date(2026, 9, 30)},
            {"version_id": self.version.id, "name": "Responsibility allowance", "kind": "allowance",
             "amount": 5000, "date_from": date(2026, 6, 1)},
        ])
        t = self._compute()
        self.assertAlmostEqual(t["FIXED_ALLOWANCE"], 5000)
        self.assertAlmostEqual(t["GROSS"], 105000)
        self.assertAlmostEqual(t["NSSF_AMOUNT"], 6300)
        self.assertAlmostEqual(t["SHIF_AMOUNT"], 2887.5)
        self.assertAlmostEqual(t["AHL_AMOUNT"], 1575)
        self.assertAlmostEqual(t["GROSS_TAXABLE"], 94237.5)
        self.assertAlmostEqual(t["PAYE"], 20654.60, places=2)
        self.assertAlmostEqual(t["HELB"], 2000)
        self.assertAlmostEqual(t["FIXED_DED"], 1000)         # the finished loan is excluded
        self.assertAlmostEqual(t["NET"], 70582.90, places=2)

    def test_helb_one_off_adjustment_adds_to_fixed_amount(self):
        self.version.ke_helb = 2000
        t = self._compute({"HELB": 500, "BONUS": 0})
        self.assertAlmostEqual(t["HELB"], 2500)
        self.assertNotIn("BONUS", t)                         # a zero input stays off the payslip

    def test_bonus_is_taxed(self):
        t = self._compute({"BONUS": 10000})
        self.assertAlmostEqual(t["BONUS"], 10000)
        self.assertAlmostEqual(t["GROSS"], 110000)
