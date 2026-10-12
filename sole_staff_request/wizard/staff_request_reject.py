# -*- coding: utf-8 -*-
from odoo import fields, models


class SoleStaffRequestReject(models.TransientModel):
    _name = "sole.staff.request.reject"
    _description = "Reject a Staff Request"

    request_id = fields.Many2one("sole.staff.request", required=True, ondelete="cascade")
    reason = fields.Text(required=True, help="Sent to the requester.")

    def action_reject(self):
        self.request_id._do_reject(self.reason)
        return {"type": "ir.actions.act_window_close"}
