# -*- coding: utf-8 -*-
from odoo import models, fields


class SoleKpiIndicator(models.Model):
    _name = 'sole.kpi.indicator'
    _description = 'KPI Indicator Definition'
    _order = 'sequence, name'

    name = fields.Char(string='KPI Name', required=True)
    category_id = fields.Many2one(
        'sole.kpi.category',
        string='Category',
        required=True,
        ondelete='restrict',
    )
    role_ids = fields.Many2many(
        'sole.kpi.role',
        'sole_kpi_indicator_role_rel',
        'indicator_id',
        'role_id',
        string='Applicable Roles',
    )
    target = fields.Float(string='Target', required=True)
    target_display = fields.Char(
        string='Target Display',
        help='Optional override shown on the dashboard, e.g. "≤2" or "4–6".',
    )
    unit = fields.Selection(
        [
            ('currency', 'KES'),
            ('percentage', '%'),
            ('count', 'Count'),
            ('hours', 'Hours'),
        ],
        string='Unit',
        default='count',
        required=True,
    )
    direction = fields.Selection(
        [
            ('higher', 'Higher is Better'),
            ('lower', 'Lower is Better'),
        ],
        string='Direction',
        default='higher',
        required=True,
    )
    weight = fields.Float(
        string='Weight',
        default=1.0,
        help='Relative weight for weighted-average scoring. Default 1.0 (equal weight).',
    )
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
