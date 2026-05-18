# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SoleSmsTemplate(models.Model):
    _name = "sole.sms.template"
    _description = "SMS Template"
    _rec_name = "name"

    name = fields.Char(string="Template Name", required=True)
    body = fields.Text(
        string="Message Body",
        required=True,
        help="Use {placeholder} syntax. Available: {customer_name}, {amount}, {ref}, {company_name}, {date}",
    )
    category = fields.Char(string="Category")
    is_active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    def render(self, values: dict) -> str:
        """Render the template with provided values dict."""
        self.ensure_one()
        body = self.body
        for key, val in values.items():
            body = body.replace("{" + key + "}", str(val or ""))
        return body
