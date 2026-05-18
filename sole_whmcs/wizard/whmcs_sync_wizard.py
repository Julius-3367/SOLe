# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SoleWhmcsSyncWizard(models.TransientModel):
    _name = "sole.whmcs.sync.wizard"
    _description = "WHMCS Sync Wizard"

    config_id = fields.Many2one(
        "sole.whmcs.config",
        string="WHMCS Config",
        required=True,
        domain=[("is_active", "=", True)],
        default=lambda self: self.env["sole.whmcs.config"].search(
            [("is_active", "=", True)], limit=1
        ),
    )
    sync_clients = fields.Boolean(string="Sync Clients", default=True)
    sync_invoices = fields.Boolean(string="Sync Invoices", default=True)

    def action_sync(self):
        self.ensure_one()
        messages = []
        if self.sync_clients:
            created, updated, errors = self.config_id.sync_clients()
            messages.append(_("Clients — Created: %d, Updated: %d, Errors: %d") % (created, updated, len(errors)))
        if self.sync_invoices:
            created, errors = self.config_id.sync_invoices()
            messages.append(_("Invoices — Created: %d, Errors: %d") % (created, len(errors)))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WHMCS Sync Complete"),
                "message": "\n".join(messages),
                "type": "success",
                "sticky": True,
            },
        }
