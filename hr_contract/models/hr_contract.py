# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    """Employee contract that links an employee to a salary structure
    and defines wage and working schedule."""
    _name = 'hr.contract'
    _description = 'Employee Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    name = fields.Char('Contract Reference', required=True, tracking=True)
    active = fields.Boolean(default=True)

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    job_id = fields.Many2one(
        'hr.job', string='Job Position',
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one(
        'hr.department', string='Department',
        domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string='Working Schedule',
        default=lambda self: self.env.company.resource_calendar_id,
        domain="[('company_id', '=', company_id)]",
        copy=True,
    )
    contract_type_id = fields.Many2one(
        'hr.contract.type', string='Contract Type',
    )
    date_start = fields.Date('Start Date', required=True,
                             default=fields.Date.today, tracking=True)
    date_end = fields.Date('End Date', tracking=True,
                           help="End date of the contract (if applicable).")
    trial_date_end = fields.Date('End of Trial Period')
    wage = fields.Monetary('Wage', required=True, tracking=True,
                           help="Employee's monthly gross wage.")
    hr_responsible_id = fields.Many2one(
        'res.users', string='HR Responsible',
        domain="[('share', '=', False)]",
        help="Person responsible for validating the employee's contracts.",
    )
    notes = fields.Html('Notes')
    state = fields.Selection([
        ('draft', 'New'),
        ('open', 'Running'),
        ('close', 'Expired'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False,
        help="Status of the contract.")

    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red'),
    ], string='Kanban State', default='normal', copy=False,
        help="State of the contract seen in kanban view.")

    # -------------------------------------------------------------------------
    # Business methods
    # -------------------------------------------------------------------------

    def action_confirm(self):
        self.write({'state': 'open'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
