# -*- coding: utf-8 -*-
"""
sole.support.ticket — Main support ticket model.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SoleSupportTicket(models.Model):
    _name = "sole.support.ticket"
    _description = "Support Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "subject"

    # ── Core fields ──────────────────────────────────────────────────────────
    name = fields.Char(
        string="Ticket #",
        readonly=True,
        default=lambda self: _("New"),
        copy=False,
    )
    subject = fields.Char(string="Subject", required=True, tracking=True)
    description = fields.Html(string="Description")
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
    )
    email = fields.Char(
        string="Customer Email",
        related="partner_id.email",
        store=True,
    )
    phone = fields.Char(
        string="Customer Phone",
        related="partner_id.phone",
        store=True,
    )
    stage_id = fields.Many2one(
        "sole.support.stage",
        string="Stage",
        required=True,
        default=lambda self: self._default_stage(),
        tracking=True,
    )
    category_id = fields.Many2one(
        "sole.support.category",
        string="Category",
        tracking=True,
    )
    priority = fields.Selection(
        [("0", "Low"), ("1", "Normal"), ("2", "High"), ("3", "Critical")],
        string="Priority",
        default="1",
        tracking=True,
    )
    assigned_to = fields.Many2one(
        "res.users",
        string="Assigned To",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    sla_deadline = fields.Datetime(string="SLA Deadline", tracking=True)
    date_closed = fields.Datetime(string="Closed On", readonly=True)
    is_portal = fields.Boolean(
        string="Submitted via Portal",
        default=False,
        readonly=True,
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Attachments",
    )
    # Kanban color
    color = fields.Integer(string="Color Index")
    kanban_state = fields.Selection(
        [
            ("normal", "In Progress"),
            ("done", "Ready for Next Stage"),
            ("blocked", "Blocked"),
        ],
        string="Kanban State",
        default="normal",
        tracking=True,
    )

    # ── Default stage ─────────────────────────────────────────────────────────
    def _default_stage(self):
        stage = self.env["sole.support.stage"].search(
            [("is_closed", "=", False)], order="sequence", limit=1
        )
        return stage.id if stage else False

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("sole.support.ticket") or _("New")
        return super().create(vals_list)

    # ── Stage change hooks ────────────────────────────────────────────────────
    def write(self, vals):
        if "stage_id" in vals:
            stage = self.env["sole.support.stage"].browse(vals["stage_id"])
            if stage.is_closed:
                vals["date_closed"] = fields.Datetime.now()
        return super().write(vals)

    # ── Actions ───────────────────────────────────────────────────────────────
    def action_assign_to_me(self):
        self.assigned_to = self.env.user

    def action_close(self):
        closed_stage = self.env["sole.support.stage"].search(
            [("is_closed", "=", True)], limit=1
        )
        if closed_stage:
            self.write({"stage_id": closed_stage.id})

    def action_resolve(self):
        resolved_stage = self.env["sole.support.stage"].search(
            [("is_resolved", "=", True)], limit=1
        )
        if resolved_stage:
            self.write({"stage_id": resolved_stage.id})

    def action_set_sla(self, hours=24):
        self.sla_deadline = fields.Datetime.now() + timedelta(hours=hours)
