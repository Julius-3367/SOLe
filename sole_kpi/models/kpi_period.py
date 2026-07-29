# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class SoleKpiPeriod(models.Model):
    _name = 'sole.kpi.period'
    _description = 'KPI Reporting Period'
    _order = 'date_start desc'

    name = fields.Char(string='Period Name', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    state = fields.Selection(
        [('draft', 'Open'), ('locked', 'Locked')],
        string='Status',
        default='draft',
        required=True,
    )
    entry_ids = fields.One2many('sole.kpi.entry', 'period_id', string='KPI Entries')
    entry_count = fields.Integer(
        string='Entries',
        compute='_compute_entry_count',
        store=False,
    )

    _unique_name = models.Constraint(
        'UNIQUE(name)',
        'A period with this name already exists.',
    )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError("End date must be after start date.")

    def _compute_entry_count(self):
        for rec in self:
            rec.entry_count = self.env['sole.kpi.entry'].search_count(
                [('period_id', '=', rec.id)]
            )

    def action_lock(self):
        for rec in self:
            rec.state = 'locked'

    def action_open(self):
        for rec in self:
            rec.state = 'draft'

    def action_view_entries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'KPI Entries – %s' % self.name,
            'res_model': 'sole.kpi.entry',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }

    def action_generate_entries(self):
        """Create KPI entry shells for every role member × every indicator in that role.

        Skips entries that already exist. Runs as sudo so record rules don't
        block managers from creating entries on behalf of users.
        """
        self.ensure_one()
        if self.state == 'locked':
            raise UserError("Cannot generate entries for a locked period.")

        Entry = self.env['sole.kpi.entry'].sudo()
        created = 0

        for role in self.env['sole.kpi.role'].search([('active', '=', True)]):
            if not role.user_ids:
                continue
            indicators = self.env['sole.kpi.indicator'].search([
                ('active', '=', True),
                ('role_ids', 'in', [role.id]),
            ])
            if not indicators:
                continue
            for user in role.user_ids:
                for indicator in indicators:
                    exists = Entry.search_count([
                        ('period_id', '=', self.id),
                        ('indicator_id', '=', indicator.id),
                        ('user_id', '=', user.id),
                    ])
                    if not exists:
                        Entry.create({
                            'period_id': self.id,
                            'indicator_id': indicator.id,
                            'user_id': user.id,
                            'role_id': role.id,
                            'actual': 0.0,
                        })
                        created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'KPI Entries Generated',
                'message': '%d entry/entries created for this period.' % created,
                'type': 'success' if created else 'warning',
                'sticky': False,
            },
        }
