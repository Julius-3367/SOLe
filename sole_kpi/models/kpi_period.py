# -*- coding: utf-8 -*-
from odoo import models, fields


class SoleKpiPeriod(models.Model):
    _name = 'sole.kpi.period'
    _description = 'KPI Reporting Period'
    _order = 'date_start desc'

    name = fields.Char(string='Period Name', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    state = fields.Selection(
        [
            ('draft', 'Open'),
            ('locked', 'Locked'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
    entry_ids = fields.One2many(
        'sole.kpi.entry',
        'period_id',
        string='KPI Entries',
    )

    _sql_constraints = [
        ('unique_name', 'UNIQUE(name)', 'A period with this name already exists.'),
    ]

    def action_lock(self):
        for rec in self:
            rec.state = 'locked'

    def action_open(self):
        for rec in self:
            rec.state = 'draft'
