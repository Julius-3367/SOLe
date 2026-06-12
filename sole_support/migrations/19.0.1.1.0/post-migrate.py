# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Collapse the legacy 5-stage pipeline (and any ad-hoc kanban
    columns) onto the new 3-stage Backlog / In Progress / Complete
    pipeline.
    """
    env = api.Environment(cr, SUPERUSER_ID, {"skip_support_project_sync": True})
    env["sole.support.stage"]._migrate_legacy_stages()
