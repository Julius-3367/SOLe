# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SoleTender(models.Model):
    _name = 'sole.tender'
    _description = 'Tender Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline_date asc, name'

    name = fields.Char(string='Tender Name', required=True, tracking=True)
    reference = fields.Char(string='Tender Ref/No.')
    issuing_org = fields.Char(
        string='Issuing Organization', required=True, tracking=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Client/Buyer', ondelete='set null'
    )
    source = fields.Selection(
        [
            ('etenders', 'eTenders Portal'),
            ('newspaper', 'Newspaper'),
            ('direct', 'Direct Contact'),
            ('referral', 'Referral'),
            ('website', 'Website'),
            ('other', 'Other'),
        ],
        string='Source',
        default='etenders',
    )
    category = fields.Selection(
        [
            ('ict', 'ICT & Software'),
            ('consulting', 'Consulting'),
            ('supply', 'Supply of Goods'),
            ('works', 'Works & Construction'),
            ('services', 'Managed Services'),
            ('other', 'Other'),
        ],
        string='Category',
        default='ict',
    )
    deadline_date = fields.Date(
        string='Submission Deadline', required=True, tracking=True
    )
    submission_date = fields.Date(string='Date Submitted', tracking=True)
    state = fields.Selection(
        [
            ('identified', 'Identified'),
            ('qualifying', 'Qualifying'),
            ('preparing', 'Preparing'),
            ('submitted', 'Submitted'),
            ('won', 'Won'),
            ('lost', 'Lost'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='identified',
        tracking=True,
        required=True,
    )
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
        ondelete='set null',
    )
    bid_value = fields.Float(string='Our Bid Value (KES)')
    contract_value = fields.Float(
        string='Contract Value (KES)',
        help='Actual awarded value if won',
    )
    description = fields.Text(string='Scope / Notes')
    go_no_go = fields.Selection(
        [
            ('pending', 'Pending Decision'),
            ('go', 'Go'),
            ('no_go', 'No Go'),
        ],
        string='Go / No-Go',
        default='pending',
    )
    days_to_deadline = fields.Integer(
        string='Days to Deadline',
        compute='_compute_days_to_deadline',
        store=False,
    )
    color = fields.Integer(string='Color Index', compute='_compute_color')

    @api.depends('deadline_date')
    def _compute_days_to_deadline(self):
        today = fields.Date.today()
        for rec in self:
            if rec.deadline_date:
                rec.days_to_deadline = (rec.deadline_date - today).days
            else:
                rec.days_to_deadline = 0

    @api.depends('state', 'days_to_deadline')
    def _compute_color(self):
        for rec in self:
            if rec.state == 'won':
                rec.color = 10
            elif rec.state in ('lost', 'cancelled'):
                rec.color = 1
            elif rec.days_to_deadline <= 3:
                rec.color = 1
            elif rec.days_to_deadline <= 7:
                rec.color = 3
            else:
                rec.color = 0

    def action_qualifying(self):
        self.write({'state': 'qualifying'})

    def action_preparing(self):
        self.write({'state': 'preparing'})

    def action_submit(self):
        self.write({
            'state': 'submitted',
            'submission_date': fields.Date.today(),
        })

    def action_won(self):
        self.write({'state': 'won'})

    def action_lost(self):
        self.write({'state': 'lost'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'identified'})
