# -*- coding: utf-8 -*-
"""Kenyan payroll fields that belong to the person rather than the contract.

Mortgage interest relief and disability exemption follow the employee, not the
job, so they stay here and survive a change of contract.
"""
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    ke_mortgage = fields.Monetary(
        string="Mortgage Interest",
        help="Monthly mortgage interest on an owner-occupied home. Deducted "
             "from taxable pay, subject to the statutory cap.",
        groups="hr.group_hr_user",
    )
    ke_disabled = fields.Boolean(
        string="Registered Disabled",
        help="Employees with a valid exemption certificate have part of their "
             "pay excluded from the Affordable Housing Levy.",
        groups="hr.group_hr_user",
    )
