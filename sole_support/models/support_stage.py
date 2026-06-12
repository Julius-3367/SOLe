# -*- coding: utf-8 -*-
from odoo import api, fields, models


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

    # Canonical 3-column pipeline: Backlog / In Progress / Complete.
    CANONICAL_XML_IDS = {
        "sole_support.stage_backlog",
        "sole_support.stage_in_progress",
        "sole_support.stage_complete",
    }

    @api.model
    def _migrate_legacy_stages(self):
        """Collapse any non-canonical stage into Backlog or Complete.

        Older installs (and ad-hoc columns added via the kanban "+") may
        have stages like "New", "Waiting on Customer", "Resolved",
        "Closed" or arbitrary user-created columns. Resolved/closed
        stages collapse onto "Complete"; everything else collapses onto
        "Backlog". Tickets are moved before the legacy stage is removed.
        """
        backlog = self.env.ref("sole_support.stage_backlog")
        complete = self.env.ref("sole_support.stage_complete")
        Ticket = self.env["sole.support.ticket"]
        for stage in self.search([]):
            ext_id = stage.get_external_id().get(stage.id, "")
            if ext_id in self.CANONICAL_XML_IDS:
                continue
            target = complete if (stage.is_resolved or stage.is_closed) else backlog
            tickets = Ticket.search([("stage_id", "=", stage.id)])
            if tickets:
                tickets.write({"stage_id": target.id})
            stage.unlink()
