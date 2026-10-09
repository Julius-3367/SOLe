# -*- coding: utf-8 -*-
from odoo import _, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    asset_ids = fields.One2many('account.asset.asset', 'employee_id', string='Assets')
    asset_count = fields.Integer(compute='_compute_asset_count', groups='account.group_account_user')

    def _compute_asset_count(self):
        counts = dict(self.env['account.asset.asset']._read_group(
            [('employee_id', 'in', self.ids)], ['employee_id'], ['__count']))
        for employee in self:
            employee.asset_count = counts.get(employee, 0)

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assets held by %s', self.name),
            'res_model': 'account.asset.asset',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id, 'default_type': 'purchase'},
        }
