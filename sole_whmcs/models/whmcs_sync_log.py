# -*- coding: utf-8 -*-
from odoo import fields, models


class SoleWhmcsSyncLog(models.Model):
    _name = "sole.whmcs.sync.log"
    _description = "WHMCS Sync Log"
    _order = "create_date desc"
    _rec_name = "create_date"

    config_id = fields.Many2one("sole.whmcs.config", string="Config", required=True, ondelete="cascade")
    sync_type = fields.Selection(
        [("clients", "Clients"), ("invoices", "Invoices"), ("full", "Full Sync")],
        string="Sync Type",
        required=True,
    )
    records_created = fields.Integer(string="Created")
    records_updated = fields.Integer(string="Updated")
    error_count = fields.Integer(string="Errors")
    errors = fields.Text(string="Error Details")
    state = fields.Selection(
        [("ok", "OK"), ("warning", "Warning"), ("error", "Error")],
        string="Status",
        compute="_compute_state",
        store=True,
    )

    def _compute_state(self):
        for rec in self:
            if rec.error_count == 0:
                rec.state = "ok"
            elif rec.records_created > 0 or rec.records_updated > 0:
                rec.state = "warning"
            else:
                rec.state = "error"
