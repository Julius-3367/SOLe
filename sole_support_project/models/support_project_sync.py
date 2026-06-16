# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Command

SKIP_SUPPORT_PROJECT_SYNC = 'skip_support_project_sync'

# Maps sole_support stage xml ids → sole_support_project task stage xml ids.
SUPPORT_TO_TASK_STAGE = {
    'stage_backlog': 'task_stage_backlog',
    'stage_in_progress': 'task_stage_in_progress',
    'stage_complete': 'task_stage_complete',
}
TASK_TO_SUPPORT_STAGE = {v: k for k, v in SUPPORT_TO_TASK_STAGE.items()}


class SupportProjectSyncMixin(models.AbstractModel):
    _name = 'sole.support.project.sync.mixin'
    _description = 'Support ↔ Project synchronization helpers'

    SKIP_SYNC_CTX = SKIP_SUPPORT_PROJECT_SYNC

    def _is_syncing_support_project(self):
        return bool(self.env.context.get(SKIP_SUPPORT_PROJECT_SYNC))

    def _support_sync_context(self):
        return {SKIP_SUPPORT_PROJECT_SYNC: True}

    def _get_support_project(self):
        return self.env.ref(
            'sole_support_project.project_support_duties',
            raise_if_not_found=False,
        )

    def _xml_suffix(self, record, module_prefix):
        ext_id = record.get_external_id().get(record.id, '')
        if ext_id.startswith(f'{module_prefix}.'):
            return ext_id.split('.', 1)[1]
        return False

    def _support_stage_to_task_stage(self, support_stage):
        if not support_stage:
            return self.env['project.task.type']
        suffix = self._xml_suffix(support_stage, 'sole_support')
        task_suffix = SUPPORT_TO_TASK_STAGE.get(suffix)
        if task_suffix:
            return self.env.ref(
                f'sole_support_project.{task_suffix}',
                raise_if_not_found=False,
            )
        project = self._get_support_project()
        if not project:
            return self.env['project.task.type']
        return self.env['project.task.type'].search([
            ('name', '=', support_stage.name),
            ('project_ids', 'in', project.ids),
        ], limit=1)

    def _task_stage_to_support_stage(self, task_stage):
        if not task_stage:
            return self.env['sole.support.stage']
        suffix = self._xml_suffix(task_stage, 'sole_support_project')
        support_suffix = TASK_TO_SUPPORT_STAGE.get(suffix)
        if support_suffix:
            return self.env.ref(
                f'sole_support.{support_suffix}',
                raise_if_not_found=False,
            )
        return self.env['sole.support.stage'].search([
            ('name', '=', task_stage.name),
        ], limit=1)

    @staticmethod
    def _priority_to_task(priority):
        return priority or '0'

    @staticmethod
    def _priority_to_support(priority):
        return priority or '0'

    @staticmethod
    def _diff_vals(record, vals):
        """Return only keys whose values differ from the current record."""
        changes = {}
        for field, value in vals.items():
            if field == 'assigned_to':
                current = record.assigned_to.id if record.assigned_to else False
                if current != (value or False):
                    changes[field] = value
                continue
            if field == 'user_ids':
                current_ids = set(record.user_ids.ids)
                if value and value[0][0] == Command.SET:
                    new_ids = set(value[0][2])
                else:
                    new_ids = set()
                if current_ids != new_ids:
                    changes[field] = value
                continue
            current = record[field]
            if hasattr(current, 'id'):
                current = current.id
            compare = value.id if hasattr(value, 'id') else value
            if current != compare:
                changes[field] = value
        return changes
