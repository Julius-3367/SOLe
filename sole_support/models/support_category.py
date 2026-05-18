# -*- coding: utf-8 -*-
from odoo import fields, models


class SoleSupportCategory(models.Model):
    _name = "sole.support.category"
    _description = "Support Ticket Category"
    _rec_name = "name"

    name = fields.Char(string="Category", required=True, translate=True)
    description = fields.Text(string="Description")
    is_active = fields.Boolean(string="Active", default=True)
