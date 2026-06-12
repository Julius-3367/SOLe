# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Collapse the Support Duties project task-type pipeline onto the new
    3-column Backlog / In Progress / Complete stages, matching the
    sole_support ticket stage migration.
    """
    env = api.Environment(cr, SUPERUSER_ID, {"skip_support_project_sync": True})
    env["project.task"]._migrate_legacy_support_task_stages()
