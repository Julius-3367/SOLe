# -*- coding: utf-8 -*-
"""
sole.sms.batch — Bulk SMS campaign model.
"""
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CHUNK_SIZE = 50  # commit to DB every N sends so a mid-batch crash doesn't lose progress


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
    scheduled_at = fields.Datetime(
        string="Schedule Send At",
        help="Leave blank to send manually. Set a date/time to have the cron send automatically.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("running", "Running"), ("done", "Done"), ("partial", "Partial"), ("failed", "Failed")],
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

    @api.model
    def _cron_send_scheduled(self):
        """Called by the hourly cron. Only processes batches whose scheduled_at has passed."""
        now = fields.Datetime.now()
        due = self.search([
            ("state", "=", "draft"),
            ("scheduled_at", "!=", False),
            ("scheduled_at", "<=", now),
        ])
        for batch in due:
            try:
                batch.action_send_all()
            except Exception:
                _logger.exception("SMS cron: failed to send batch %s (%s)", batch.id, batch.name)

    def action_send_all(self):
        """Send SMS to all pending recipients, committing every CHUNK_SIZE sends."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one recipient before sending."))
        self.write({"state": "running"})
        self.env.cr.commit()

        company_name = self.env.company.name or ""
        today = fields.Date.today().strftime("%Y-%m-%d")
        pending_lines = self.line_ids.filtered(lambda l: l.state == "draft")
        chunk = []
        log_vals_bulk = []

        def _flush(lines, logs):
            if logs:
                self.env["sole.sms.log"].create(logs)
            for line, state, err in lines:
                line.write({"state": state, "error": err})
            self.env.cr.commit()

        for line in pending_lines:
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
            chunk.append((line, "sent" if success else "failed", error))
            log_vals_bulk.append({
                "provider_id": self.provider_id.id,
                "phone": line.phone,
                "message": msg,
                "provider_msg_id": msg_id,
                "state": "sent" if success else "failed",
                "error": error,
                "batch_id": self.id,
                "partner_id": line.partner_id.id if line.partner_id else False,
            })

            if len(chunk) >= CHUNK_SIZE:
                _flush(chunk, log_vals_bulk)
                chunk = []
                log_vals_bulk = []

        if chunk:
            _flush(chunk, log_vals_bulk)

        # Recompute stats and set final state
        self._compute_stats()
        if self.failed_count == 0:
            final_state = "done"
        elif self.sent_count == 0:
            final_state = "failed"
        else:
            final_state = "partial"
        self.write({"state": final_state})
        self.env.cr.commit()

        notif_type = "success" if final_state == "done" else ("warning" if final_state == "partial" else "danger")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Batch Complete"),
                "message": _("Sent: %d  Failed: %d") % (self.sent_count, self.failed_count),
                "type": notif_type,
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
