# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SoleKpiEntry(models.Model):
    _name = 'sole.kpi.entry'
    _description = 'KPI Entry / Measurement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_id desc, indicator_id'

    period_id = fields.Many2one(
        'sole.kpi.period',
        string='Period',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    indicator_id = fields.Many2one(
        'sole.kpi.indicator',
        string='KPI Indicator',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Staff Member',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
        tracking=True,
    )
    role_id = fields.Many2one(
        'sole.kpi.role',
        string='Role',
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
        string='Unit',
        related='indicator_id.unit',
        store=True,
        readonly=True,
    )
    direction = fields.Selection(
        string='Direction',
        related='indicator_id.direction',
        store=True,
        readonly=True,
    )
    actual = fields.Float(string='Actual', default=0.0, tracking=True)
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
            ('up', 'Improving'),
            ('stable', 'Stable'),
            ('down', 'Declining'),
        ],
        string='Trend',
    )
    notes = fields.Text(string='Notes')

    _unique_period_indicator_user = models.Constraint(
        'UNIQUE(period_id, indicator_id, user_id)',
        'An entry for this KPI, period, and staff member already exists.',
    )

    @api.constrains('period_id', 'indicator_id', 'user_id')
    def _check_unique_period_indicator_user(self):
        for rec in self:
            if self.search_count([
                ('period_id', '=', rec.period_id.id),
                ('indicator_id', '=', rec.indicator_id.id),
                ('user_id', '=', rec.user_id.id),
                ('id', '!=', rec.id),
            ]):
                raise ValidationError(
                    "An entry for this KPI, period, and staff member already exists."
                )

    @api.depends('actual', 'target', 'indicator_id.direction')
    def _compute_achievement(self):
        for rec in self:
            if not rec.target:
                rec.achievement_pct = 0.0
                rec.status = 'grey'
                continue
            direction = rec.indicator_id.direction or 'higher'
            if direction == 'lower':
                pct = 100.0 if rec.actual <= rec.target else (
                    (rec.target / rec.actual) * 100.0 if rec.actual > 0 else 0.0
                )
            else:
                pct = (rec.actual / rec.target) * 100.0
            rec.achievement_pct = pct
            if pct >= 80:
                rec.status = 'green'
            elif pct >= 70:
                rec.status = 'amber'
            elif pct >= 60:
                rec.status = 'red'
            else:
                rec.status = 'black'
