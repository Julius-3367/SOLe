# -*- coding: utf-8 -*-
"""
sole.whmcs.config — WHMCS API connection and sync engine.

WHMCS API v1 uses POST with action, identifier, secret and responsetype=json.
"""
import logging
from datetime import datetime

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)



class SoleWhmcsConfig(models.Model):
    _name = "sole.whmcs.config"
    _description = "WHMCS API Configuration"
    _rec_name = "name"

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)", "A config with this name already exists for this company."),
    ]

    name = fields.Char(string="Config Name", required=True, default="WHMCS Connection")
    api_url = fields.Char(
        string="WHMCS API URL",
        required=True,
        help="e.g. https://billing.yourdomain.com/includes/api.php",
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
        help="Account used when creating invoice lines from WHMCS.",
    )
    default_journal_id = fields.Many2one(
        "account.journal",
        string="Invoice Journal",
        domain=[("type", "=", "sale")],
    )
    payment_journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        domain=[("type", "in", ("bank", "cash"))],
        help="Journal the WHMCS payment is recorded against when a paid invoice is imported.",
    )
    sale_tax_id = fields.Many2one(
        "account.tax",
        string="VAT",
        domain=[("type_tax_use", "=", "sale")],
        help="Applied to the WHMCS subtotal when the WHMCS invoice carries tax.",
    )
    import_from_date = fields.Date(
        string="Import Paid Invoices From",
        help="Paid WHMCS invoices dated before this are not imported. Required before syncing invoices.",
    )
    last_client_sync = fields.Datetime(string="Last Client Sync", readonly=True)
    last_invoice_sync = fields.Datetime(string="Last Invoice Sync", readonly=True)
    sync_log_count = fields.Integer(string="Sync Logs", compute="_compute_log_count")

    def _compute_log_count(self):
        for rec in self:
            rec.sync_log_count = self.env["sole.whmcs.sync.log"].search_count(
                [("config_id", "=", rec.id)]
            )

    @api.constrains("api_url")
    def _check_api_url(self):
        for rec in self:
            if rec.api_url and not rec.api_url.startswith(("http://", "https://")):
                raise UserError(_("API URL must start with http:// or https://"))

    # ── API Call ─────────────────────────────────────────────────────────────
    def _api_call(self, action, extra_params=None):
        """Execute a WHMCS API call. Returns the decoded JSON response dict."""
        self.ensure_one()
        if not _REQUESTS_OK:
            raise UserError(
                _("The Python 'requests' library is not installed. "
                  "Run: pip install requests")
            )
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

    def action_sync_full(self):
        """Convenience button: sync clients then invoices, show result."""
        self.ensure_one()
        c_created, c_updated, c_errors = self.sync_clients()
        i_created, i_errors = self.sync_invoices()
        lines = [
            _("Clients — Created: %d, Updated: %d, Errors: %d") % (c_created, c_updated, len(c_errors)),
            _("Invoices — Created: %d, Errors: %d") % (i_created, len(i_errors)),
        ]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WHMCS Sync Complete"),
                "message": "\n".join(lines),
                "type": "success" if not (c_errors or i_errors) else "warning",
                "sticky": True,
            },
        }

    # ── Client Sync ──────────────────────────────────────────────────────────
    def sync_clients(self, limit_per_page=100):
        """Import WHMCS clients as Odoo partners.

        Deduplication: first by whmcs_client_id, then by email as fallback.
        """
        self.ensure_one()
        offset = 0
        total_created = 0
        total_updated = 0
        errors = []
        Partner = self.env["res.partner"].sudo()
        Country = self.env["res.country"].sudo()
        _country_cache = {}

        def _get_country(code):
            if not code:
                return False
            code = code.upper()
            if code not in _country_cache:
                country = Country.search([("code", "=", code)], limit=1)
                _country_cache[code] = country.id if country else False
            return _country_cache[code]

        while True:
            try:
                data = self._api_call("GetClients", {
                    "limitstart": offset,
                    "limitnum": limit_per_page,
                })
            except UserError as exc:
                errors.append(str(exc))
                break

            clients = (data.get("clients") or {}).get("client") or []
            if not clients:
                break
            if isinstance(clients, dict):
                clients = [clients]

            for client in clients:
                whmcs_id = str(client.get("id", "")).strip()
                if not whmcs_id:
                    continue
                try:
                    existing = Partner.search(
                        [("whmcs_client_id", "=", whmcs_id)], limit=1
                    )
                    # Fallback: match by email so we don't duplicate known contacts
                    if not existing and client.get("email"):
                        existing = Partner.search(
                            [("email", "=", client["email"]), ("whmcs_client_id", "=", False)],
                            limit=1,
                        )

                    company = (client.get("companyname") or "").strip()
                    person = f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
                    vals = {
                        "name": company or person or "Unknown",
                        "email": client.get("email", ""),
                        "phone": client.get("phonenumber", ""),
                        "street": client.get("address1", ""),
                        "street2": client.get("address2", ""),
                        "city": client.get("city", ""),
                        "zip": client.get("postcode", ""),
                        "country_id": _get_country(client.get("countrycode", "")),
                        "is_company": bool(company),
                        "customer_rank": 1,
                        "whmcs_client_id": whmcs_id,
                    }

                    if existing:
                        # Odoo is the record accounts maintain: link it and fill gaps, never overwrite
                        existing.write({
                            k: v for k, v in vals.items()
                            if k == "whmcs_client_id" or (v and not existing[k])
                        })
                        total_updated += 1
                    else:
                        Partner.create(vals)
                        total_created += 1
                except Exception as exc:
                    errors.append(f"Client {whmcs_id}: {exc}")

            offset += len(clients)
            if offset >= self._total_results(data, "clients"):
                break

        self.last_client_sync = fields.Datetime.now()
        self._log_sync("clients", total_created, total_updated, errors)
        return total_created, total_updated, errors

    # ── Invoice Sync ─────────────────────────────────────────────────────────
    def sync_invoices(self, limit_per_page=100):
        """Import paid WHMCS invoices as posted, paid Odoo customer invoices.

        Unpaid, cancelled and refunded invoices stay in WHMCS. Invoices already
        imported (ref WHMCS-INV-{id}) or dated before import_from_date are skipped.
        Invoices settled partly or fully from WHMCS credit are skipped and listed
        in the sync log for manual entry.
        """
        self.ensure_one()
        missing = [
            label for label, value in (
                (_("Invoice Journal"), self.default_journal_id),
                (_("Payment Journal"), self.payment_journal_id),
                (_("Import Paid Invoices From"), self.import_from_date),
            ) if not value
        ]
        if missing:
            raise UserError(_("Set these on the WHMCS configuration before syncing invoices: %s") % ", ".join(missing))
        offset = 0
        total_created = 0
        errors = []
        Move = self.env["account.move"].sudo()
        Partner = self.env["res.partner"].sudo()
        Currency = self.env["res.currency"].sudo()

        while True:
            try:
                data = self._api_call("GetInvoices", {
                    "limitstart": offset,
                    "limitnum": limit_per_page,
                    "status": "Paid",
                })
            except UserError as exc:
                errors.append(str(exc))
                break

            invoices = (data.get("invoices") or {}).get("invoice") or []
            if not invoices:
                break
            if isinstance(invoices, dict):
                invoices = [invoices]

            for inv in invoices:
                whmcs_inv_id = str(inv.get("id", "")).strip()
                if not whmcs_inv_id:
                    continue
                ref = f"WHMCS-INV-{whmcs_inv_id}"
                invoice_date = self._parse_date(inv.get("date"))
                if not invoice_date or invoice_date < self.import_from_date:
                    continue
                if Move.search([("ref", "=", ref)], limit=1):
                    continue  # already imported

                subtotal = float(inv.get("subtotal") or 0)
                tax = float(inv.get("tax") or 0) + float(inv.get("tax2") or 0)
                total = float(inv.get("total") or 0)
                if not subtotal:
                    continue  # zero-value invoice, nothing to book
                if abs(subtotal + tax - total) > 0.01:
                    errors.append(f"Invoice {whmcs_inv_id}: paid from WHMCS credit "
                                  f"(subtotal {subtotal:.2f} + tax {tax:.2f}, paid {total:.2f}), enter manually")
                    continue
                if tax and not self.sale_tax_id:
                    errors.append(f"Invoice {whmcs_inv_id}: carries tax but no VAT is set on the WHMCS configuration")
                    continue

                client_id = str(inv.get("userid", "")).strip()
                partner = (
                    Partner.search([("whmcs_client_id", "=", client_id)], limit=1)
                    if client_id else Partner.browse()
                )
                if not partner:
                    errors.append(f"Invoice {whmcs_inv_id}: WHMCS client {client_id or '?'} not in Odoo, run client sync first")
                    continue

                try:
                    with self.env.cr.savepoint():
                        move_vals = {
                            "move_type": "out_invoice",
                            "partner_id": partner.id,
                            "journal_id": self.default_journal_id.id,
                            "ref": ref,
                            "invoice_date": invoice_date,
                            "invoice_date_due": self._parse_date(inv.get("duedate")) or invoice_date,
                            "invoice_line_ids": [(0, 0, {
                                "name": f"WHMCS Invoice #{whmcs_inv_id}",
                                "quantity": 1,
                                "price_unit": subtotal,
                                "account_id": self.default_account_id.id if self.default_account_id else False,
                                "tax_ids": [(6, 0, self.sale_tax_id.ids if tax else [])],
                            })],
                            "narration": "WHMCS Status: Paid",
                        }
                        currency = Currency.search([("name", "=", inv.get("currencycode"))], limit=1)
                        if currency:
                            move_vals["currency_id"] = currency.id
                        move = Move.create(move_vals)
                        if abs(move.amount_total - total) > 0.01:
                            raise UserError(f"Odoo total {move.amount_total:.2f} does not match WHMCS total {total:.2f}")
                        move.action_post()
                        self.env["account.payment.register"].sudo().with_context(
                            active_model="account.move", active_ids=move.ids,
                        ).create({
                            "journal_id": self.payment_journal_id.id,
                            "payment_date": self._parse_date(inv.get("datepaid")) or invoice_date,
                        })._create_payments()
                    total_created += 1
                except Exception as exc:
                    _logger.exception("WHMCS: failed to import invoice %s", whmcs_inv_id)
                    errors.append(f"Invoice {whmcs_inv_id}: {exc}")

            offset += len(invoices)
            if offset >= self._total_results(data, "invoices"):
                break

        self.last_invoice_sync = fields.Datetime.now()
        self._log_sync("invoices", total_created, 0, errors)
        return total_created, errors

    @staticmethod
    def _total_results(data, key):
        # WHMCS returns totalresults at the top level, not inside the list block
        return int(data.get("totalresults") or (data.get(key) or {}).get("totalresults") or 0)

    @staticmethod
    def _parse_date(value):
        """Parse a WHMCS date string (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) to a date."""
        if not value:
            return False
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(str(value).strip(), fmt).date()
            except ValueError:
                continue
        _logger.warning("WHMCS: could not parse date %r", value)
        return False

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
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
        }
