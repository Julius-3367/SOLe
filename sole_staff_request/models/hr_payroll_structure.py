# -*- coding: utf-8 -*-
from odoo import api, models


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    @api.model
    def _sole_link_staff_advance_rule(self):
        """Put STAFF_ADVANCE on the Kenyan structure.

        Run on every install and upgrade of this module: the structure is
        sole_payroll_ke's noupdate data, and reloading it there resets its rules.
        """
        structure = self.env.ref("sole_payroll_ke.structure_ke", raise_if_not_found=False)
        rule = self.env.ref("sole_staff_request.rule_staff_advance", raise_if_not_found=False)
        if structure and rule and rule not in structure.rule_ids:
            structure.rule_ids = [(4, rule.id)]
