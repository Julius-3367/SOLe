# -*- coding: utf-8 -*-
from odoo import models, fields


class SoleKpiRole(models.Model):
    _name = 'sole.kpi.role'
    _description = 'KPI Staff Role'
    _order = 'name'

    name = fields.Char(string='Role Name', required=True)
    code = fields.Char(string='Code', required=True)
    user_ids = fields.Many2many(
        'res.users',
        'sole_kpi_role_user_rel',
        'role_id',
        'user_id',
        string='Assigned Users',
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
