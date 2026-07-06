# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    whmcs_client_id = fields.Char(
        string="WHMCS Client ID",
        index=True,
        copy=False,
        help="Numeric WHMCS client ID used to match partners during sync. Do not edit.",
    )
