# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

SMS_SINGLE_LIMIT = 160
SMS_MULTI_LIMIT = 153  # per segment when message is multi-part


class SoleSendSmsWizard(models.TransientModel):
    _name = "sole.send.sms.wizard"
    _description = "Send SMS Wizard"

    provider_id = fields.Many2one(
        "sole.sms.provider",
        string="Provider",
        required=True,
        domain=[("is_active", "=", True)],
        default=lambda self: self.env["sole.sms.provider"].search(
            [("is_active", "=", True)], limit=1
        ),
    )
    template_id = fields.Many2one("sole.sms.template", string="Template")
    phone = fields.Char(string="Phone Number", required=True)
    message = fields.Text(string="Message", required=True)
    partner_id = fields.Many2one("res.partner", string="Customer")
    char_count = fields.Integer(string="Characters", compute="_compute_char_info")
    sms_segments = fields.Integer(string="SMS Parts", compute="_compute_char_info")

    @api.depends("message")
    def _compute_char_info(self):
        for rec in self:
            length = len(rec.message or "")
            rec.char_count = length
            if length <= SMS_SINGLE_LIMIT:
                rec.sms_segments = 1 if length > 0 else 0
            else:
                import math
                rec.sms_segments = math.ceil(length / SMS_MULTI_LIMIT)

    @api.onchange("template_id")
    def _onchange_template(self):
        if self.template_id:
            self.message = self.template_id.body

    def action_send(self):
        self.ensure_one()
        if not self.message:
            raise UserError(_("Message cannot be empty."))
        success, msg_id, error = self.provider_id.send_sms(self.phone, self.message)
        self.env["sole.sms.log"].create({
            "provider_id": self.provider_id.id,
            "phone": self.provider_id._normalize_phone(self.phone),
            "message": self.message,
            "provider_msg_id": msg_id,
            "state": "sent" if success else "failed",
            "error": error,
            "partner_id": self.partner_id.id if self.partner_id else False,
        })
        notif_type = "success" if success else "danger"
        notif_msg = _("SMS sent successfully to %s") % self.phone if success else _("SMS failed: %s") % error
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("SMS"), "message": notif_msg, "type": notif_type},
        }
