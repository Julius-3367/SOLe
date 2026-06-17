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
        group_expand="_read_group_stage_ids",
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
    # ── Escalation ────────────────────────────────────────────────────────────
    is_escalated = fields.Boolean(
        string="Escalated",
        default=False,
        tracking=True,
    )
    escalated_to = fields.Many2one(
        "res.users",
        string="Escalated To",
        tracking=True,
    )
    escalation_reason = fields.Text(
        string="Escalation Reason",
        tracking=True,
    )
    escalated_date = fields.Datetime(
        string="Escalated On",
        readonly=True,
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

    # ── Kanban grouping ──────────────────────────────────────────────────────
    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Always show every stage as a kanban column, even when empty."""
        return stages.search([], order="sequence, id")

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("sole.support.ticket") or _("New")
        records = super().create(vals_list)
        for record in records:
            if record.assigned_to:
                record._notify_assigned(record.assigned_to)
        return records

    # ── Stage change hooks ────────────────────────────────────────────────────
    def write(self, vals):
        prev_assigned = {r.id: r.assigned_to for r in self} if "assigned_to" in vals else {}
        if "stage_id" in vals:
            stage = self.env["sole.support.stage"].browse(vals["stage_id"])
            if stage.is_closed:
                vals["date_closed"] = fields.Datetime.now()
        result = super().write(vals)
        if "assigned_to" in vals and vals["assigned_to"]:
            new_user = self.env["res.users"].browse(vals["assigned_to"])
            for record in self:
                if record.assigned_to != prev_assigned.get(record.id):
                    record._notify_assigned(new_user)
        return result

    def _notify_assigned(self, user):
        """Subscribe the user as a follower and send the assignment email."""
        if not user or not user.partner_id:
            return
        self.message_subscribe(partner_ids=[user.partner_id.id])
        template = self.env.ref(
            "sole_support.mail_template_ticket_assigned", raise_if_not_found=False
        )
        if template and user.email:
            template.send_mail(self.id, force_send=False)

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

    def action_escalate(self):
        """Escalate the ticket: set flag, bump priority to at least High, log chatter."""
        for ticket in self:
            # Bump priority to at least High if currently Low or Normal
            if ticket.priority in ("0", "1"):
                ticket.priority = "2"
            ticket.write({
                "is_escalated": True,
                "escalated_date": fields.Datetime.now(),
            })
            ticket.message_post(
                body=_("Ticket escalated by %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_note",
            )

    def action_deescalate(self):
        """Remove escalation flag and log chatter."""
        for ticket in self:
            ticket.write({
                "is_escalated": False,
                "escalated_to": False,
                "escalation_reason": False,
                "escalated_date": False,
            })
            ticket.message_post(
                body=_("Escalation removed by %s.") % self.env.user.name,
                subtype_xmlid="mail.mt_note",
            )
