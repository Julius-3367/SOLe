# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.fields import Command


class SoleSupportTicket(models.Model):
    _name = 'sole.support.ticket'
    _inherit = ['sole.support.ticket', 'sole.support.project.sync.mixin']

    task_id = fields.Many2one(
        'project.task',
        string='Project Task',
        copy=False,
        readonly=True,
        index=True,
    )
    task_count = fields.Integer(compute='_compute_task_count')

    @api.depends('task_id')
    def _compute_task_count(self):
        for ticket in self:
            ticket.task_count = 1 if ticket.task_id else 0

    def _prepare_project_task_vals(self):
        self.ensure_one()
        project = self._get_support_project()
        if not project:
            return False
        task_stage = self._support_stage_to_task_stage(self.stage_id)
        return {
            'name': self._task_name(),
            'project_id': project.id,
            'partner_id': self.partner_id.id,
            'description': self.description,
            'stage_id': task_stage.id if task_stage else False,
            'user_ids': [Command.set(self.assigned_to.ids)] if self.assigned_to else [Command.clear()],
            'priority': self._priority_to_task(self.priority),
            'date_deadline': self.sla_deadline,
            'support_ticket_id': self.id,
        }

    def _task_name(self):
        self.ensure_one()
        return f'[{self.name}] {self.subject}'

    def _prepare_task_sync_vals(self):
        self.ensure_one()
        task_stage = self._support_stage_to_task_stage(self.stage_id)
        return {
            'name': self._task_name(),
            'partner_id': self.partner_id.id,
            'description': self.description,
            'stage_id': task_stage.id if task_stage else False,
            'user_ids': [Command.set(self.assigned_to.ids)] if self.assigned_to else [Command.clear()],
            'priority': self._priority_to_task(self.priority),
            'date_deadline': self.sla_deadline,
        }

    def _sync_to_project_task(self):
        if self._is_syncing_support_project():
            return
        ctx = self._support_sync_context()
        for ticket in self.filtered('task_id'):
            changes = ticket._diff_vals(ticket.task_id, ticket._prepare_task_sync_vals())
            if changes:
                ticket.task_id.with_context(**ctx).write(changes)

    def _ensure_project_task(self):
        if self._is_syncing_support_project():
            return
        ctx = self._support_sync_context()
        Task = self.env['project.task'].with_context(**ctx)
        for ticket in self.filtered('assigned_to'):
            if ticket.task_id:
                ticket._sync_to_project_task()
                continue
            vals = ticket._prepare_project_task_vals()
            if not vals:
                continue
            ticket.with_context(**ctx).write({'task_id': Task.create(vals).id})

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        tickets.filtered('assigned_to')._ensure_project_task()
        return tickets

    def write(self, vals):
        if self._is_syncing_support_project():
            return super().write(vals)
        res = super().write(vals)
        sync_fields = {'assigned_to', 'stage_id', 'subject', 'description', 'partner_id', 'priority', 'sla_deadline'}
        if sync_fields & set(vals):
            self._ensure_project_task()
            self.filtered('task_id')._sync_to_project_task()
        return res

    def action_assign_to_me(self):
        res = super().action_assign_to_me()
        self._ensure_project_task()
        return res

    def action_view_project_task(self):
        self.ensure_one()
        if not self.task_id:
            self._ensure_project_task()
        if not self.task_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Task'),
            'res_model': 'project.task',
            'view_mode': 'form',
            'res_id': self.task_id.id,
            'context': {'default_project_id': self.task_id.project_id.id},
        }
