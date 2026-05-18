# -*- coding: utf-8 -*-
import logging
from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SoleSmsLog(models.Model):
    _name = "sole.sms.log"
    _description = "SMS Outbound Log"
    _order = "create_date desc"
    _rec_name = "phone"

    provider_id = fields.Many2one("sole.sms.provider", string="Provider", required=True)
    phone = fields.Char(string="Recipient Phone", required=True)
    message = fields.Text(string="Message")
    provider_msg_id = fields.Char(string="Provider Message ID", index=True)
    state = fields.Selection(
        [("sent", "Sent"), ("failed", "Failed"), ("delivered", "Delivered")],
        string="Status",
        default="sent",
        index=True,
    )
    error = fields.Char(string="Error")
    partner_id = fields.Many2one("res.partner", string="Partner")
    res_model = fields.Char(string="Related Model")
    res_id = fields.Integer(string="Related Record ID")
    batch_id = fields.Many2one("sole.sms.batch", string="Batch")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="provider_id.company_id",
        store=True,
    )
