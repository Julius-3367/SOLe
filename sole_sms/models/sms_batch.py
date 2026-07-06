# -*- coding: utf-8 -*-
"""
sole.sms.batch — Bulk SMS campaign model.
"""
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Commit to DB every N sends so a mid-batch crash doesn't lose all progress.
COMMIT_CHUNK = 50
# Batches larger than this are too big to process synchronously in one HTTP
# request — schedule them for background execution via the cron instead.
BACKGROUND_THRESHOLD = 500


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
        [("draft", "Draft"), ("queued", "Queued"), ("running", "Running"),
         ("done", "Done"), ("partial", "Partial"), ("failed", "Failed")],
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
        """Called by the cron. Processes scheduled batches and background-queued batches."""
        now = fields.Datetime.now()
        # Draft batches with a past/current scheduled_at
        due_scheduled = self.search([
            ("state", "=", "draft"),
            ("scheduled_at", "!=", False),
            ("scheduled_at", "<=", now),
        ])
        # Batches queued for background processing by action_send_all
        due_queued = self.search([("state", "=", "queued")])
        due = due_scheduled | due_queued
        for batch in due:
            try:
                batch._execute_send()
            except Exception:
                _logger.exception("SMS cron: failed to send batch %s (%s)", batch.id, batch.name)

    def action_send_all(self):
        """Send SMS to all recipients.

        Batches with more than BACKGROUND_THRESHOLD pending recipients are
        too large to process synchronously — they are queued for the background
        cron so the browser request doesn't time out.
        """
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one recipient before sending."))

        pending_count = len(self.line_ids.filtered(lambda l: l.state == "draft"))
        if pending_count > BACKGROUND_THRESHOLD:
            # Mark as queued so the cron picks it up within 5 minutes.
            self.write({"state": "queued", "scheduled_at": fields.Datetime.now()})
            self.env.cr.commit()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Batch Queued"),
                    "message": _(
                        "%d recipients — too large to send inline. "
                        "The batch will be processed in the background within 5 minutes."
                    ) % pending_count,
                    "type": "warning",
                },
            }

        return self._execute_send()

    def _execute_send(self):
        """Core send loop — called by action_send_all (small batches) and cron (all sizes)."""
        self.ensure_one()
        self.write({"state": "running"})
        self.env.cr.commit()

        company_name = self.env.company.name or ""
        today = fields.Date.today().strftime("%Y-%m-%d")
        pending_lines = self.line_ids.filtered(lambda l: l.state == "draft")

        # Build (normalised_phone, rendered_message) for each line
        normalize = self.env["sole.sms.provider"]._normalize_phone
        recipients = []
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
            recipients.append((normalize(line.phone), msg, line))

        # Send in bulk via the provider (1 API call per 100 recipients for Onfon)
        # Commit to DB every COMMIT_CHUNK sends for crash safety.
        for chunk_start in range(0, len(recipients), COMMIT_CHUNK):
            chunk = recipients[chunk_start: chunk_start + COMMIT_CHUNK]
            phones_msgs = [(phone, msg) for phone, msg, _ in chunk]
            results = self.provider_id.send_sms_bulk(phones_msgs)

            log_vals_list = []
            for (phone, msg, line), (success, msg_id, error) in zip(chunk, results):
                line.write({"state": "sent" if success else "failed", "error": error})
                log_vals_list.append({
                    "provider_id": self.provider_id.id,
                    "phone": phone,
                    "message": msg,
                    "provider_msg_id": msg_id,
                    "state": "sent" if success else "failed",
                    "error": error,
                    "batch_id": self.id,
                    "partner_id": line.partner_id.id if line.partner_id else False,
                })
            if log_vals_list:
                self.env["sole.sms.log"].create(log_vals_list)
            self.env.cr.commit()

        # Final state
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
