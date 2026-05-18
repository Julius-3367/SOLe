# -*- coding: utf-8 -*-
"""
Bank statement import wizard.

Parses CSV files from common Kenyan bank formats and creates
sole.bank.statement.import + sole.bank.recon.line records.
"""
import base64
import csv
import io
import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _parse_date(date_str, formats=None):
    formats = formats or [
        "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y",
        "%d %b %Y", "%d-%b-%Y", "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _parse_amount(value):
    """Convert strings like '1,234.56' or '-500' to float."""
    try:
        return float(str(value).replace(",", "").strip() or "0")
    except (ValueError, TypeError):
        return 0.0


class SoleBankImportWizard(models.TransientModel):
    _name = "sole.bank.import.wizard"
    _description = "Bank Statement Import Wizard"

    journal_id = fields.Many2one(
        "account.journal",
        string="Bank Journal",
        required=True,
        domain=[("type", "=", "bank")],
    )
    bank_format = fields.Selection(
        [
            ("mpesa", "M-Pesa"),
            ("equity", "Equity Bank"),
            ("kcb", "KCB Bank"),
            ("coop", "Co-operative Bank"),
            ("generic", "Generic CSV (Date, Desc, Debit, Credit, Balance)"),
        ],
        string="Statement Format",
        required=True,
        default="generic",
    )
    csv_file = fields.Binary(string="CSV File", required=True, attachment=False)
    csv_filename = fields.Char(string="Filename")
    import_name = fields.Char(string="Import Name", required=True,
                               default=lambda self: f"Import {fields.Date.today()}")
    skip_rows = fields.Integer(string="Skip Header Rows", default=1)

    def action_import(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_("Please upload a CSV file."))
        try:
            raw = base64.b64decode(self.csv_file).decode("utf-8-sig", errors="replace")
        except Exception as exc:
            raise UserError(_("Could not decode file: %s") % exc) from exc

        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
        # Skip header rows
        rows = rows[self.skip_rows:]

        lines = []
        errors = []
        for i, row in enumerate(rows, start=self.skip_rows + 1):
            if not any(cell.strip() for cell in row):
                continue
            try:
                line_vals = self._parse_row(row)
                if line_vals:
                    lines.append(line_vals)
            except Exception as exc:
                errors.append(f"Row {i}: {exc}")

        if errors and not lines:
            raise UserError(_("Import failed:\n") + "\n".join(errors[:10]))

        stmt = self.env["sole.bank.statement.import"].create({
            "name": self.import_name,
            "journal_id": self.journal_id.id,
            "bank_format": self.bank_format,
        })
        for lv in lines:
            lv["import_id"] = stmt.id
            self.env["sole.bank.recon.line"].create(lv)

        if errors:
            _logger.warning("Bank import partial errors: %s", errors)

        return {
            "type": "ir.actions.act_window",
            "name": _("Imported Statement"),
            "res_model": "sole.bank.statement.import",
            "res_id": stmt.id,
            "view_mode": "form",
        }

    def _parse_row(self, row):
        """Dispatch to the correct parser based on bank_format."""
        parsers = {
            "mpesa": self._parse_mpesa,
            "equity": self._parse_equity,
            "kcb": self._parse_kcb,
            "coop": self._parse_coop,
            "generic": self._parse_generic,
        }
        return parsers[self.bank_format](row)

    # ── M-Pesa Statement ──────────────────────────────────────────────────────
    # Columns: Receipt No | Completion Time | Details | Transaction Status | Paid In | Withdrawn | Balance
    def _parse_mpesa(self, row):
        if len(row) < 7:
            return None
        ref = row[0].strip()
        date_str = row[1].strip()
        desc = row[2].strip()
        status = row[3].strip()
        paid_in = _parse_amount(row[4])
        withdrawn = _parse_amount(row[5])
        balance = _parse_amount(row[6]) if len(row) > 6 else 0.0
        if status.lower() not in ("completed", "success", ""):
            return None
        txn_date = _parse_date(date_str)
        if not txn_date:
            return None
        return {
            "transaction_date": txn_date,
            "description": desc,
            "ref": ref,
            "credit": paid_in,
            "debit": withdrawn,
            "balance": balance,
        }

    # ── Equity Bank Statement ─────────────────────────────────────────────────
    # Columns: Date | Description | Debit | Credit | Balance
    def _parse_equity(self, row):
        if len(row) < 5:
            return None
        txn_date = _parse_date(row[0])
        if not txn_date:
            return None
        return {
            "transaction_date": txn_date,
            "description": row[1].strip(),
            "ref": row[1].strip()[:50],
            "debit": _parse_amount(row[2]),
            "credit": _parse_amount(row[3]),
            "balance": _parse_amount(row[4]) if len(row) > 4 else 0.0,
        }

    # ── KCB Bank Statement ────────────────────────────────────────────────────
    # Columns: Value Date | Transaction Date | Description | Reference | Debit | Credit | Balance
    def _parse_kcb(self, row):
        if len(row) < 7:
            return None
        txn_date = _parse_date(row[1]) or _parse_date(row[0])
        if not txn_date:
            return None
        return {
            "transaction_date": txn_date,
            "description": row[2].strip(),
            "ref": row[3].strip()[:50],
            "debit": _parse_amount(row[4]),
            "credit": _parse_amount(row[5]),
            "balance": _parse_amount(row[6]),
        }

    # ── Co-op Bank Statement ──────────────────────────────────────────────────
    # Columns: Posting Date | Value Date | Description | Reference | Amount | Balance
    def _parse_coop(self, row):
        if len(row) < 6:
            return None
        txn_date = _parse_date(row[0])
        if not txn_date:
            return None
        amount = _parse_amount(row[4])
        return {
            "transaction_date": txn_date,
            "description": row[2].strip(),
            "ref": row[3].strip()[:50],
            "debit": abs(amount) if amount < 0 else 0.0,
            "credit": amount if amount > 0 else 0.0,
            "balance": _parse_amount(row[5]),
        }

    # ── Generic CSV ───────────────────────────────────────────────────────────
    # Columns: Date | Description | Debit | Credit | Balance
    def _parse_generic(self, row):
        if len(row) < 4:
            return None
        txn_date = _parse_date(row[0])
        if not txn_date:
            return None
        return {
            "transaction_date": txn_date,
            "description": row[1].strip() if len(row) > 1 else "",
            "ref": "",
            "debit": _parse_amount(row[2]) if len(row) > 2 else 0.0,
            "credit": _parse_amount(row[3]) if len(row) > 3 else 0.0,
            "balance": _parse_amount(row[4]) if len(row) > 4 else 0.0,
        }
