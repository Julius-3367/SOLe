# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """Link existing assigned support tickets to project tasks."""
    tickets = env['sole.support.ticket'].search([
        ('assigned_to', '!=', False),
        ('task_id', '=', False),
    ])
    if tickets:
        tickets._ensure_project_task()
