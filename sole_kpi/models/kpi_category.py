# -*- coding: utf-8 -*-
from odoo import models, fields


class SoleKpiCategory(models.Model):
    _name = 'sole.kpi.category'
    _description = 'KPI Strategic Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(string='Active', default=True)
