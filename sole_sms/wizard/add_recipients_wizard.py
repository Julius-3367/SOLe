# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class SoleSmsAddRecipientsWizard(models.TransientModel):
    _name = "sole.sms.add.recipients.wizard"
    _description = "Add SMS Recipients from Contacts"

    batch_id = fields.Many2one(
        "sole.sms.batch", string="Batch", required=True, ondelete="cascade"
    )
    source = fields.Selection(
        [("filter", "Filter Contacts"), ("manual", "Pick Contacts")],
        string="Source",
        default="filter",
        required=True,
    )
    customers_only = fields.Boolean(
        string="Customers Only",
        default=True,
        help="Only include contacts marked as a customer (Customer Rank > 0).",
    )
    category_ids = fields.Many2many(
        "res.partner.category",
        string="Contact Tags",
        help="Limit to contacts having any of these tags. Leave empty for all.",
    )
    partner_ids = fields.Many2many(
        "res.partner", string="Contacts", help="Used when Source = Pick Contacts."
    )
    skip_existing = fields.Boolean(
        string="Skip Already-Added Numbers",
        default=True,
        help="Don't add a contact if its phone number is already in the batch's recipient list.",
    )
    match_count = fields.Integer(string="Matched Contacts", compute="_compute_counts")
    with_phone_count = fields.Integer(string="With Phone Number", compute="_compute_counts")

    @api.depends("source", "customers_only", "category_ids", "partner_ids")
    def _compute_counts(self):
        for wiz in self:
            partners = wiz._get_partners()
            wiz.match_count = len(partners)
            wiz.with_phone_count = len(partners.filtered(lambda p: p.phone))

    def _get_partners(self):
        self.ensure_one()
        if self.source == "manual":
            return self.partner_ids
        domain = []
        if self.customers_only:
            domain.append(("customer_rank", ">", 0))
        if self.category_ids:
            domain.append(("category_id", "in", self.category_ids.ids))
        return self.env["res.partner"].search(domain)

    def action_add(self):
        self.ensure_one()
        partners = self._get_partners()
        normalize = self.env["sole.sms.provider"]._normalize_phone

        seen = set()
        if self.skip_existing:
            seen.update(normalize(line.phone) for line in self.batch_id.line_ids)

        added = 0
        skipped_no_phone = 0
        skipped_duplicate = 0
        line_vals = []
        for partner in partners:
            phone = partner.phone
            if not phone:
                skipped_no_phone += 1
                continue
            norm = normalize(phone)
            if norm in seen:
                skipped_duplicate += 1
                continue
            seen.add(norm)
            line_vals.append({
                "batch_id": self.batch_id.id,
                "phone": phone,
                "name": partner.name,
                "partner_id": partner.id,
            })
            added += 1

        if line_vals:
            self.env["sole.sms.batch.line"].create(line_vals)

        message = _("Added %d recipient(s).") % added
        details = []
        if skipped_duplicate:
            details.append(_("%d already in batch") % skipped_duplicate)
        if skipped_no_phone:
            details.append(_("%d without a phone number") % skipped_no_phone)
        if details:
            message += " (" + ", ".join(details) + ")"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Recipients Added"),
                "message": message,
                "type": "success" if added else "warning",
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "sole.sms.batch",
                    "res_id": self.batch_id.id,
                    "views": [[False, "form"]],
                    "target": "current",
                },
            },
        }
