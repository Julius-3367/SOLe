# -*- coding: utf-8 -*-
"""
account.move extension — show M-Pesa payment details and
Kenya-specific fields on customer invoices.
"""
from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # ── M-Pesa Payment Reference on Invoice ─────────────────────
    mpesa_paybill = fields.Char(
        string="M-Pesa Paybill / Till",
        compute="_compute_mpesa_paybill",
        store=False,
        help="M-Pesa Paybill or Till number to display on invoice.",
    )
    mpesa_account_ref = fields.Char(
        string="M-Pesa Account Ref",
        compute="_compute_mpesa_paybill",
        store=False,
        help="What the customer should enter as account reference when paying via M-Pesa.",
    )

    @api.depends("company_id")
    def _compute_mpesa_paybill(self):
        """Pull M-Pesa config from the active config for this company."""
        for move in self:
            config = self.env["sole.mpesa.config"].search([
                ("company_id", "=", move.company_id.id),
                ("is_active", "=", True),
            ], limit=1)
            move.mpesa_paybill = config.shortcode if config else ""
            move.mpesa_account_ref = move.name or ""


class SoleKenyaCounty(models.Model):
    """Kenya county reference data."""
    _name = "sole.kenya.county"
    _description = "Kenya County"
    _order = "name"

    name = fields.Char(string="County", required=True)
    code = fields.Char(string="Code", size=3)
    partner_ids = fields.One2many("res.partner", "kenya_county_id", string="Partners")
