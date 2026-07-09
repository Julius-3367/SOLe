# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentTag(models.Model):
    _name = 'document.tag'
    _description = 'Document Tag'
    _order = 'name'

    name = fields.Char('Tag Name', required=True, translate=True)
    color = fields.Integer('Color Index', default=0)

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'A tag with this name already exists.'),
    ]
