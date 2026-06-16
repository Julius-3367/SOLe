# -*- coding: utf-8 -*-

from odoo import models, fields

class PropertyTag(models.Model):
    _name = 'insafety.property.tag'
    _description = 'Real Estate Property Tags'
    name = fields.Char(string="Name", required=True)
    color = fields.Integer(string="Color")

    name_uniq = models.Constraint('UNIQUE(name)', 'Property tag already exists')
    