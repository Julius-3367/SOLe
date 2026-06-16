# -*- coding: utf-8 -*-

from odoo import fields, models

class PropertyType(models.Model):
    _name = 'insafety.property.type'
    _description = 'Real Estate Property Types'
    name = fields.Char(string="Name", required=True)

    name_uniq = models.Constraint('UNIQUE(name)', 'Property type already exists')
    
   

