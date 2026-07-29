# -*- coding: utf-8 -*-
from odoo import models, fields

# Odoo color-picker widget maps integer indices 0-11 to these colours.
ODOO_COLOR_MAP = {
    0: '#e4e3e3', 1: '#f06050', 2: '#f4a460', 3: '#f7cd1f',
    4: '#6cc1ed', 5: '#814968', 6: '#eb7e7f', 7: '#2c8397',
    8: '#475577', 9: '#d46a6a', 10: '#85a69b', 11: '#7d7c7c',
}


class SoleKpiCategory(models.Model):
    _name = 'sole.kpi.category'
    _description = 'KPI Strategic Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color Index', default=0)
    color_hex = fields.Char(
        string='Color (Hex)',
        compute='_compute_color_hex',
        store=False,
    )
    active = fields.Boolean(string='Active', default=True)

    def _compute_color_hex(self):
        for rec in self:
            rec.color_hex = ODOO_COLOR_MAP.get(rec.color, '#e4e3e3')
