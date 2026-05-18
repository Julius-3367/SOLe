# -*- coding: utf-8 -*-
"""
sole.whmcs.config — WHMCS API connection and sync engine.

WHMCS API v1 uses POST with action, identifier, secret and responsetype=json.
"""
import logging
from datetime import datetime

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SoleWhmcsConfig(models.Model):
    _name = "sole.whmcs.config"
    _description = "WHMCS API Configuration"
    _rec_name = "name"

    name = fields.Char(string="Config Name", required=True, default="WHMCS Connection")
    api_url = fields.Char(
        string="WHMCS API URL",
        required=True,
        help="e.g. https://yourdomain.com/includes/api.php",
    )
    api_identifier = fields.Char(string="API Identifier", required=True)
    api_secret = fields.Char(string="API Secret", required=True)
    is_active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    default_account_id = fields.Many2one(
        "account.account",
        string="Default Revenue Account",
        help="Account used when creating invoices from WHMCS.",
    )
    default_journal_id = fields.Many2one(
        "account.journal",
        string="Invoice Journal",
        domain=[("type", "=", "sale")],
    )
    last_client_sync = fields.Datetime(string="Last Client Sync", readonly=True)
    last_invoice_sync = fields.Datetime(string="Last Invoice Sync", readonly=True)

    sync_log_count = fields.Integer(string="Sync Logs", compute="_compute_log_count")

    def _compute_log_count(self):
        for rec in self:
            rec.sync_log_count = self.env["sole.whmcs.sync.log"].search_count(
                [("config_id", "=", rec.id)]
            )

    # ── API Call ─────────────────────────────────────────────────────────────
    def _api_call(self, action, extra_params=None):
        """Execute a WHMCS API call. Returns the decoded JSON response dict."""
        self.ensure_one()
        payload = {
            "action": action,
            "identifier": self.api_identifier,
            "secret": self.api_secret,
            "responsetype": "json",
        }
        if extra_params:
            payload.update(extra_params)
        try:
            resp = requests.post(self.api_url, data=payload, timeout=30, verify=True)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("WHMCS API request failed: %s") % exc) from exc
        data = resp.json()
        if data.get("result") == "error":
            raise UserError(_("WHMCS API error: %s") % data.get("message", str(data)))
        return data

    def action_test_connection(self):
        """Test the WHMCS API credentials."""
        self.ensure_one()
        data = self._api_call("GetSystemURL")
        url = data.get("systemurl", "unknown")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WHMCS Connected"),
                "message": _("Connected to WHMCS at: %s") % url,
                "type": "success",
            },
        }

    # ── Client Sync ──────────────────────────────────────────────────────────
    def sync_clients(self, limit_per_page=100):
        """Import WHMCS clients as Odoo partners."""
        self.ensure_one()
        offset = 0
        total_created = 0
        total_updated = 0
        errors = []
        Partner = self.env["res.partner"].sudo()

        while True:
            try:
                data = self._api_call("GetClients", {
                    "limitstart": offset,
                    "limitnum": limit_per_page,
                })
            except UserError as exc:
                errors.append(str(exc))
                break

            clients = data.get("clients", {}).get("client", [])
            if not clients:
                break
            if isinstance(clients, dict):
                clients = [clients]

            for client in clients:
                whmcs_id = str(client.get("id", ""))
                email = client.get("email", "")
                existing = Partner.search(
                    [("comment", "like", f"WHMCS ID: {whmcs_id}")], limit=1
                ) if whmcs_id else Partner.browse()

                vals = {
                    "name": f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                            or client.get("companyname", "Unknown"),
                    "email": email,
                    "phone": client.get("phonenumber", ""),
                    "street": client.get("address1", ""),
                    "street2": client.get("address2", ""),
                    "city": client.get("city", ""),
                    "zip": client.get("postcode", ""),
                    "is_company": bool(client.get("companyname", "")),
                    "comment": f"WHMCS ID: {whmcs_id}",
                    "customer_rank": 1,
                }
                if existing:
                    existing.write(vals)
                    total_updated += 1
                else:
                    Partner.create(vals)
                    total_created += 1

            total_in_page = data.get("clients", {}).get("totalresults", 0)
            offset += limit_per_page
            if offset >= int(total_in_page):
                break

        self.last_client_sync = datetime.utcnow()
        self._log_sync("clients", total_created, total_updated, errors)
        return total_created, total_updated, errors

    # ── Invoice Sync ─────────────────────────────────────────────────────────
    def sync_invoices(self, limit_per_page=100):
        """Import WHMCS invoices as Odoo customer invoices."""
        self.ensure_one()
        if not self.default_journal_id:
            raise UserError(_("Please set an Invoice Journal before syncing invoices."))
        offset = 0
        total_created = 0
        errors = []
        Move = self.env["account.move"].sudo()
        Partner = self.env["res.partner"].sudo()

        while True:
            try:
                data = self._api_call("GetInvoices", {
                    "limitstart": offset,
                    "limitnum": limit_per_page,
                })
            except UserError as exc:
                errors.append(str(exc))
                break

            invoices = data.get("invoices", {}).get("invoice", [])
            if not invoices:
                break
            if isinstance(invoices, dict):
                invoices = [invoices]

            for inv in invoices:
                whmcs_inv_id = str(inv.get("id", ""))
                ref = f"WHMCS-INV-{whmcs_inv_id}"
                if Move.search([("ref", "=", ref)], limit=1):
                    continue  # already imported

                # Find partner
                client_id = str(inv.get("userid", ""))
                partner = Partner.search(
                    [("comment", "like", f"WHMCS ID: {client_id}")], limit=1
                )

                try:
                    invoice_lines = []
                    for item in (inv.get("items", {}).get("item", []) or []):
                        if isinstance(item, dict):
                            invoice_lines.append((0, 0, {
                                "name": item.get("description", "WHMCS Service"),
                                "quantity": float(item.get("quantity", 1)),
                                "price_unit": float(item.get("amount", 0)),
                                "account_id": self.default_account_id.id if self.default_account_id else False,
                            }))

                    if not invoice_lines:
                        invoice_lines = [(0, 0, {
                            "name": f"WHMCS Invoice #{whmcs_inv_id}",
                            "quantity": 1,
                            "price_unit": float(inv.get("total", 0)),
                            "account_id": self.default_account_id.id if self.default_account_id else False,
                        })]

                    move_vals = {
                        "move_type": "out_invoice",
                        "partner_id": partner.id if partner else False,
                        "journal_id": self.default_journal_id.id,
                        "ref": ref,
                        "invoice_date": inv.get("date", fields.Date.today()),
                        "invoice_line_ids": invoice_lines,
                    }
                    Move.create(move_vals)
                    total_created += 1
                except Exception as exc:
                    errors.append(f"Invoice {whmcs_inv_id}: {exc}")

            total_in_page = data.get("invoices", {}).get("totalresults", 0)
            offset += limit_per_page
            if offset >= int(total_in_page):
                break

        self.last_invoice_sync = datetime.utcnow()
        self._log_sync("invoices", total_created, 0, errors)
        return total_created, errors

    def _log_sync(self, sync_type, created, updated, errors):
        self.env["sole.whmcs.sync.log"].sudo().create({
            "config_id": self.id,
            "sync_type": sync_type,
            "records_created": created,
            "records_updated": updated,
            "error_count": len(errors),
            "errors": "\n".join(errors) if errors else "",
        })

    def action_view_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Logs"),
            "res_model": "sole.whmcs.sync.log",
            "view_mode": "list",
            "domain": [("config_id", "=", self.id)],
        }
