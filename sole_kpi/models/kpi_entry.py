# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SoleKpiEntry(models.Model):
    _name = 'sole.kpi.entry'
    _description = 'KPI Entry / Measurement'
    _order = 'period_id desc, indicator_id'

    period_id = fields.Many2one(
        'sole.kpi.period',
        string='Period',
        required=True,
        ondelete='cascade',
    )
    indicator_id = fields.Many2one(
        'sole.kpi.indicator',
        string='KPI Indicator',
        required=True,
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Staff Member',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    role_id = fields.Many2one(
        'sole.kpi.role',
        string='Role',
        help='Role this entry belongs to',
        ondelete='set null',
    )
    category_id = fields.Many2one(
        'sole.kpi.category',
        string='Category',
        related='indicator_id.category_id',
        store=True,
        readonly=True,
    )
    target = fields.Float(
        string='Target',
        related='indicator_id.target',
        store=True,
        readonly=True,
    )
    unit = fields.Selection(
        [
            ('currency', 'KES'),
            ('percentage', '%'),
            ('count', 'Count'),
            ('hours', 'Hours'),
        ],
        string='Unit',
        related='indicator_id.unit',
        store=True,
        readonly=True,
    )
    direction = fields.Selection(
        [('higher', 'Higher is Better'), ('lower', 'Lower is Better')],
        string='Direction',
        related='indicator_id.direction',
        store=True,
        readonly=True,
    )
    actual = fields.Float(string='Actual', default=0.0)
    achievement_pct = fields.Float(
        string='Achievement %',
        compute='_compute_achievement',
        store=True,
    )
    status = fields.Selection(
        [
            ('green', 'Green'),
            ('amber', 'Amber'),
            ('red', 'Red'),
            ('black', 'Black'),
            ('grey', 'No Data'),
        ],
        string='Status',
        compute='_compute_achievement',
        store=True,
    )
    trend = fields.Selection(
        [
            ('up', '▲ Improving'),
            ('stable', '► Stable'),
            ('down', '▼ Declining'),
        ],
        string='Trend',
    )
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        (
            'unique_period_indicator_user',
            'UNIQUE(period_id, indicator_id, user_id)',
            'An entry for this KPI, period, and staff member already exists.',
        ),
    ]

    @api.depends('actual', 'target', 'indicator_id.direction')
    def _compute_achievement(self):
        for rec in self:
            if not rec.target:
                rec.achievement_pct = 0.0
                rec.status = 'grey'
                continue
            if rec.indicator_id.direction == 'lower':
                if rec.actual <= rec.target:
                    pct = 100.0
                elif rec.actual > 0:
                    pct = (rec.target / rec.actual) * 100.0
                else:
                    pct = 0.0
            else:
                pct = (rec.actual / rec.target) * 100.0 if rec.target else 0.0
            rec.achievement_pct = pct
            if pct >= 80:
                rec.status = 'green'
            elif pct >= 70:
                rec.status = 'amber'
            elif pct >= 60:
                rec.status = 'red'
            else:
                rec.status = 'black'
