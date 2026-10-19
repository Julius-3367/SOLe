# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # same restriction as passport_id; hr.employee.public never sees it
    passport_copy = fields.Binary(string="Passport Copy", groups="hr.group_hr_user", copy=False)
    passport_copy_name = fields.Char(groups="hr.group_hr_user", copy=False)
