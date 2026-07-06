# -*- coding: utf-8 -*-
"""
sole.sms.batch — Bulk SMS campaign model.
"""
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SoleSmsBatch(models.Model):
    _name = "sole.sms.batch"
    _description = "Bulk SMS Batch"
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(string="Batch Name", required=True)
    provider_id = fields.Many2one(
        "sole.sms.provider",
        string="Provider",
        required=True,
        domain=[("is_active", "=", True)],
    )
    template_id = fields.Many2one("sole.sms.template", string="Template")
    message = fields.Text(string="Message Body", required=True)
    state = fields.Selection(
        [("draft", "Draft"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")],
        string="Status",
        default="draft",
    )
    line_ids = fields.One2many("sole.sms.batch.line", "batch_id", string="Recipients")
    total_count = fields.Integer(string="Total", compute="_compute_stats", store=True)
    sent_count = fields.Integer(string="Sent", compute="_compute_stats", store=True)
    failed_count = fields.Integer(string="Failed", compute="_compute_stats", store=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    @api.depends("line_ids.state")
    def _compute_stats(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_count = len(lines)
            rec.sent_count = len(lines.filtered(lambda l: l.state == "sent"))
            rec.failed_count = len(lines.filtered(lambda l: l.state == "failed"))

    @api.onchange("template_id")
    def _onchange_template(self):
        if self.template_id:
            self.message = self.template_id.body

    def action_send_all(self):
        """Send SMS to all recipients in this batch."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one recipient before sending."))
        self.state = "running"
        company_name = self.env.company.name or ""
        today = fields.Date.today().strftime("%Y-%m-%d")
        for line in self.line_ids.filtered(lambda l: l.state == "draft"):
            ctx = {
                "customer_name": line.name or "",
                "company_name": company_name,
                "date": today,
                "amount": "",
                "ref": "",
            }
            msg = self.message
            for k, v in ctx.items():
                msg = msg.replace("{" + k + "}", v)
            success, msg_id, error = self.provider_id.send_sms(line.phone, msg)
            log_vals = {
                "provider_id": self.provider_id.id,
                "phone": line.phone,
                "message": msg,
                "provider_msg_id": msg_id,
                "state": "sent" if success else "failed",
                "error": error,
                "batch_id": self.id,
                "partner_id": line.partner_id.id if line.partner_id else False,
            }
            self.env["sole.sms.log"].create(log_vals)
            line.state = "sent" if success else "failed"
        self.state = "done"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Batch Complete"),
                "message": _("Sent: %d  Failed: %d") % (self.sent_count, self.failed_count),
                "type": "success" if self.failed_count == 0 else "warning",
            },
        }


class SoleSmsBatchLine(models.Model):
    _name = "sole.sms.batch.line"
    _description = "Bulk SMS Recipient Line"
    _rec_name = "phone"

    batch_id = fields.Many2one("sole.sms.batch", string="Batch", required=True, ondelete="cascade")
    phone = fields.Char(string="Phone", required=True)
    name = fields.Char(string="Name")
    partner_id = fields.Many2one("res.partner", string="Partner")
    state = fields.Selection(
        [("draft", "Pending"), ("sent", "Sent"), ("failed", "Failed")],
        string="Status",
        default="draft",
    )
    error = fields.Char(string="Error")
