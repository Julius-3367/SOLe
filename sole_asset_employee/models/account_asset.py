# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAssetAsset(models.Model):
    _inherit = 'account.asset.asset'

    employee_id = fields.Many2one(
        'hr.employee', string='Assigned Employee', index=True, tracking=True,
        check_company=True,
        help="Who holds or is responsible for the asset. It can be changed at any time; "
             "each change is recorded in the chatter.",
    )
    department_id = fields.Many2one(
        related='employee_id.department_id', string='Department', store=True,
    )
