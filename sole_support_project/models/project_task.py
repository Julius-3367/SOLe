# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'sole.support.project.sync.mixin']

    support_ticket_id = fields.Many2one(
        'sole.support.ticket',
        string='Support Ticket',
        copy=False,
        index=True,
        ondelete='set null',
    )

    def _prepare_support_sync_vals(self):
        self.ensure_one()
        ticket = self.support_ticket_id
        support_stage = self._task_stage_to_support_stage(self.stage_id)
        vals = {
            'assigned_to': self.user_ids[:1].id if self.user_ids else False,
            'partner_id': self.partner_id.id,
            'description': self.description,
            'priority': self._priority_to_support(self.priority),
        }
        if support_stage:
            vals['stage_id'] = support_stage.id
        elif self.state in ('1_done', '03_approved'):
            resolved = self.env.ref('sole_support.stage_resolved', raise_if_not_found=False)
            if resolved:
                vals['stage_id'] = resolved.id
        elif self.state == '1_canceled':
            closed = self.env.ref('sole_support.stage_closed', raise_if_not_found=False)
            if closed:
                vals['stage_id'] = closed.id
        if self.name and ticket.name:
            prefix = f'[{ticket.name}] '
            if self.name.startswith(prefix):
                vals['subject'] = self.name[len(prefix):]
        return vals

    def _sync_to_support_ticket(self):
        if self._is_syncing_support_project():
            return
        ctx = self._support_sync_context()
        for task in self.filtered('support_ticket_id'):
            changes = task._diff_vals(task.support_ticket_id, task._prepare_support_sync_vals())
            if changes:
                task.support_ticket_id.with_context(**ctx).write(changes)

    def write(self, vals):
        if self._is_syncing_support_project():
            return super().write(vals)
        res = super().write(vals)
        sync_fields = {'stage_id', 'user_ids', 'name', 'description', 'partner_id', 'priority', 'state'}
        if sync_fields & set(vals):
            self.filtered('support_ticket_id')._sync_to_support_ticket()
        return res
