# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.fields import Command


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
    sla_deadline = fields.Datetime(
        string='SLA Deadline',
        related='support_ticket_id.sla_deadline',
        readonly=True,
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
        elif self.state in ('1_done', '03_approved', '1_canceled'):
            complete = self.env.ref('sole_support.stage_complete', raise_if_not_found=False)
            if complete:
                vals['stage_id'] = complete.id
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

    # ── Migration helper ────────────────────────────────────────────────────
    CANONICAL_TASK_STAGE_XML_IDS = {
        'sole_support_project.task_stage_backlog',
        'sole_support_project.task_stage_in_progress',
        'sole_support_project.task_stage_complete',
    }

    @api.model
    def _migrate_legacy_support_task_stages(self):
        """Collapse the Support Duties project onto the new 3-column
        Backlog / In Progress / Complete task-type pipeline.

        Tasks left on a non-canonical stage (the old New / Waiting on
        Customer / Resolved / Closed types, ad-hoc kanban columns, or no
        stage at all) are moved onto Backlog or Complete depending on
        whether the old stage was folded (done-like). The now-unused
        legacy stage types are detached from the project and removed if
        no other project still references them.
        """
        project = self.env.ref('sole_support_project.project_support_duties', raise_if_not_found=False)
        if not project:
            return
        backlog = self.env.ref('sole_support_project.task_stage_backlog')
        complete = self.env.ref('sole_support_project.task_stage_complete')

        # Tasks with no stage at all (e.g. unmapped during a prior sync).
        self.search([
            ('project_id', '=', project.id),
            ('stage_id', '=', False),
        ]).write({'stage_id': backlog.id})

        Type = self.env['project.task.type']
        legacy_types = Type.search([('project_ids', 'in', project.ids)])
        for stage_type in legacy_types:
            ext_id = stage_type.get_external_id().get(stage_type.id, '')
            if ext_id in self.CANONICAL_TASK_STAGE_XML_IDS:
                continue
            target = complete if stage_type.fold else backlog
            tasks = self.search([
                ('project_id', '=', project.id),
                ('stage_id', '=', stage_type.id),
            ])
            if tasks:
                tasks.write({'stage_id': target.id})
            stage_type.write({'project_ids': [Command.unlink(project.id)]})
            if not stage_type.project_ids:
                stage_type.unlink()
