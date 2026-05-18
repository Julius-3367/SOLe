# -*- coding: utf-8 -*-
"""
res.partner extension — Kenyan-market fields.
Adds KRA PIN and Kenya county selector.
"""
import re
import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_KRA_PIN_RE = re.compile(r'^[A-Z]\d{9}[A-Z]$')


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ── KRA Tax Compliance ──────────────────────────────────────
    kra_pin = fields.Char(
        string="KRA PIN",
        size=11,
        help="Kenya Revenue Authority Personal Identification Number. "
             "Format: A000000000B (11 characters)",
        tracking=True,
    )
    kenya_county_id = fields.Many2one(
        "sole.kenya.county",
        string="County",
        help="Kenya county (one of the 47 counties)",
    )
    is_vat_registered = fields.Boolean(
        string="VAT Registered",
        help="Tick if this customer/supplier is VAT-registered in Kenya.",
    )

    @api.constrains("kra_pin")
    def _check_kra_pin(self):
        for rec in self:
            if rec.kra_pin and not _KRA_PIN_RE.match(rec.kra_pin.upper()):
                raise ValidationError(_(
                    "Invalid KRA PIN '%(pin)s'. "
                    "Expected format: one letter, 9 digits, one letter (e.g. A123456789B).",
                    pin=rec.kra_pin,
                ))

    @api.onchange("kra_pin")
    def _onchange_kra_pin(self):
        if self.kra_pin:
            self.kra_pin = self.kra_pin.upper().strip()
