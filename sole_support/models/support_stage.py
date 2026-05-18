# -*- coding: utf-8 -*-
from odoo import fields, models


class SoleSupportStage(models.Model):
    _name = "sole.support.stage"
    _description = "Support Ticket Stage"
    _order = "sequence, id"

    name = fields.Char(string="Stage Name", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", default=10)
    is_closed = fields.Boolean(string="Closed Stage", default=False)
    is_resolved = fields.Boolean(string="Resolved Stage", default=False)
    fold = fields.Boolean(string="Folded in Kanban", default=False)
    description = fields.Text(string="Notes")
