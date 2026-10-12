# -*- coding: utf-8 -*-
from odoo import models


class HrVersion(models.Model):
    _inherit = "hr.version"

    def sole_staff_advance_due(self, date_to):
        """Paid advances waiting to be deducted on a payslip ending `date_to`.

        Called from the STAFF_ADVANCE salary rule, where `contract` is this record.
        """
        self.ensure_one()
        requests = self.env["sole.staff.request"]._advances_to_recover(self.employee_id, date_to)
        return sum(requests.mapped("amount"))
