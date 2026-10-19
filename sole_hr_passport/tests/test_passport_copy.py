# -*- coding: utf-8 -*-
import base64

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestPassportCopy(TransactionCase):

    def test_hr_officer_can_upload(self):
        officer = new_test_user(self.env, login="pp_officer", groups="base.group_user,hr.group_hr_user")
        emp = self.env["hr.employee"].with_user(officer).create({"name": "Passport Holder", "passport_id": "AK1234567"})
        scan = base64.b64encode(b"%PDF-1.4 passport scan")
        emp.write({"passport_copy": scan, "passport_copy_name": "passport.pdf"})
        self.assertEqual(emp.passport_copy, scan)
        self.assertEqual(emp.passport_copy_name, "passport.pdf")

    def test_not_visible_outside_hr(self):
        self.assertNotIn("passport_copy", self.env["hr.employee.public"]._fields)
        emp = self.env["hr.employee"].create({
            "name": "Someone", "passport_copy": base64.b64encode(b"x"), "passport_copy_name": "p.pdf",
        })
        staff = new_test_user(self.env, login="pp_staff", groups="base.group_user")
        with self.assertRaises(AccessError):
            emp.with_user(staff).read(["passport_copy"])
