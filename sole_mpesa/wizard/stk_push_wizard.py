# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SoleStkPushWizard(models.TransientModel):
    _name = "sole.stk.push.wizard"
    _description = "Send STK Push Payment Request"

    config_id = fields.Many2one(
        "sole.mpesa.config",
        string="M-Pesa Config",
        required=True,
        domain=[("is_active", "=", True)],
        default=lambda self: self.env["sole.mpesa.config"].search(
            [("is_active", "=", True)], limit=1
        ),
    )
    phone = fields.Char(string="Phone Number", required=True, help="Customer phone, e.g. 0712345678")
    amount = fields.Float(string="Amount (KES)", required=True, digits=(16, 2))
    account_ref = fields.Char(string="Account Reference", required=True)
    transaction_desc = fields.Char(string="Description", default="Payment")
    partner_id = fields.Many2one("res.partner", string="Customer")

    def action_send(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Amount must be greater than zero."))
        response = self.config_id.action_stk_push(
            phone=self.phone,
            amount=self.amount,
            account_ref=self.account_ref,
            transaction_desc=self.transaction_desc or "Payment",
        )
        checkout_id = response.get("CheckoutRequestID", "")
        merchant_id = response.get("MerchantRequestID", "")
        self.env["sole.mpesa.transaction"].create({
            "config_id": self.config_id.id,
            "transaction_type": "stk_push",
            "phone": self.config_id._normalize_phone(self.phone),
            "amount": self.amount,
            "account_ref": self.account_ref,
            "transaction_desc": self.transaction_desc,
            "merchant_request_id": merchant_id,
            "checkout_request_id": checkout_id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "state": "pending",
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("STK Push Sent"),
                "message": _(
                    "Payment request sent to %s. The customer will receive a prompt on their phone."
                ) % self.phone,
                "type": "success",
                "sticky": False,
            },
        }
