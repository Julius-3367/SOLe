# -*- coding: utf-8 -*-
# Dynamic Cash Flow Statement – Indirect Method
# Part of SOLe Accounting Suite
import io
import json
from datetime import timedelta
import xlsxwriter
from odoo import api, fields, models
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter, subtract


class DynamicCashFlowStatement(models.TransientModel):
    """Dynamic Cash Flow Statement rendered using the Indirect Method.

    Structure:
      A. Operating Activities  = Net Income + Non-cash adjustments + Working-capital changes
      B. Investing Activities  = Changes in long-term asset accounts
      C. Financing Activities  = Changes in equity and long-term liability accounts
      Net Change in Cash       = A + B + C
      Verified against closing cash = opening cash + period movement in asset_cash accounts.
    """

    _name = 'dynamic.cash.flow.statement'
    _description = 'Dynamic Cash Flow Statement'

    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company)
    journal_ids = fields.Many2many(
        'account.journal', string='Journals', required=True, default=[])
    target_move = fields.Selection(
        [('posted', 'Posted'), ('draft', 'Draft')],
        string='Target Move', required=True, default='posted')
    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')

    @api.model_create_multi
    def create(self, vals):
        return super().create({})

    # ── helpers ─────────────────────────────────────────────────────────────

    def _aml(self, account_types, date_from=None, date_to=None, target_move=None):
        """Return filtered account.move.line recordset."""
        if target_move is None:
            target_move = ['posted']
        domain = [
            ('parent_state', 'in', target_move),
            ('account_id.account_type', 'in', account_types),
        ]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))
        return self.env['account.move.line'].search(domain)

    def _net_db_cr(self, account_types, date_from=None, date_to=None, target_move=None):
        """Net debit-credit movement.
        Positive  → net debit  (asset-normal growth / expense).
        Negative  → net credit (liability/equity/income growth).
        """
        lines = self._aml(account_types, date_from, date_to, target_move)
        return sum(lines.mapped('debit')) - sum(lines.mapped('credit'))

    # ── main report ─────────────────────────────────────────────────────────

    @api.model
    def view_report(self, option):
        rec = self.browse(option)
        tm = ['posted', 'draft'] if rec.target_move == 'draft' else ['posted']
        df, dt = rec.date_from, rec.date_to

        # ── NET INCOME / (LOSS) ──────────────────────────────────────────────
        # Income accounts are credit-normal: credit-debit = positive income
        income_mv = rec._net_db_cr(['income', 'income_other'], df, dt, tm)
        income = -income_mv  # negate so positive = income earned

        # Expense accounts are debit-normal: debit-credit = positive expense
        expense = rec._net_db_cr(
            ['expense', 'expense_depreciation', 'expense_direct_cost'], df, dt, tm)

        net_income = income - expense

        # ── NON-CASH: DEPRECIATION & AMORTISATION ───────────────────────────
        depreciation = rec._net_db_cr(['expense_depreciation'], df, dt, tm)

        # ── WORKING CAPITAL CHANGES ──────────────────────────────────────────
        # Asset increase = debit-credit positive → cash outflow → effect = -change
        wc_recv = -(rec._net_db_cr(['asset_receivable'], df, dt, tm))
        wc_prep = -(rec._net_db_cr(['asset_prepayments'], df, dt, tm))
        wc_curr_asset = -(rec._net_db_cr(['asset_current'], df, dt, tm))
        # Liability increase = credit-debit positive → credit-debit negative net_db_cr
        # i.e. _net_db_cr returns negative → -negative = positive cash inflow
        wc_payables = -(rec._net_db_cr(['liability_payable'], df, dt, tm))
        wc_cc = -(rec._net_db_cr(['liability_credit_card'], df, dt, tm))
        wc_curr_liab = -(rec._net_db_cr(['liability_current'], df, dt, tm))

        net_operating = (
            net_income + depreciation
            + wc_recv + wc_prep + wc_curr_asset
            + wc_payables + wc_cc + wc_curr_liab
        )

        # ── INVESTING ACTIVITIES ─────────────────────────────────────────────
        # Fixed asset purchase: asset grew (positive net_db_cr) = cash outflow
        inv_fixed = -(rec._net_db_cr(['asset_fixed'], df, dt, tm))
        inv_nca = -(rec._net_db_cr(['asset_non_current'], df, dt, tm))

        net_investing = inv_fixed + inv_nca

        # ── FINANCING ACTIVITIES ─────────────────────────────────────────────
        # Equity increase (credit-normal) → _net_db_cr negative → -negative = positive inflow
        fin_equity = -(rec._net_db_cr(['equity'], df, dt, tm))
        fin_retained = -(rec._net_db_cr(['equity_unaffected'], df, dt, tm))
        fin_lt_liab = -(rec._net_db_cr(['liability_non_current'], df, dt, tm))

        net_financing = fin_equity + fin_retained + fin_lt_liab

        # ── CASH SUMMARY ─────────────────────────────────────────────────────
        net_change = net_operating + net_investing + net_financing

        # Opening cash: balance of asset_cash accounts BEFORE date_from
        open_domain = [
            ('parent_state', 'in', tm),
            ('account_id.account_type', '=', 'asset_cash'),
        ]
        if df:
            open_domain.append(('date', '<', df))
        if rec.journal_ids:
            open_domain.append(('journal_id', 'in', rec.journal_ids.ids))
        open_lines = self.env['account.move.line'].search(open_domain)
        opening_cash = sum(open_lines.mapped('debit')) - sum(open_lines.mapped('credit'))

        period_cash_mv = rec._net_db_cr(['asset_cash'], df, dt, tm)
        closing_cash = opening_cash + period_cash_mv

        def fmt(v):
            return "{:,.2f}".format(v)

        data = {
            'net_income': fmt(net_income),
            'depreciation': fmt(depreciation),
            'wc_receivables': fmt(wc_recv),
            'wc_prepayments': fmt(wc_prep),
            'wc_current_assets': fmt(wc_curr_asset),
            'wc_payables': fmt(wc_payables),
            'wc_credit_card': fmt(wc_cc),
            'wc_current_liabilities': fmt(wc_curr_liab),
            'net_operating': fmt(net_operating),
            'invest_fixed': fmt(inv_fixed),
            'invest_non_current': fmt(inv_nca),
            'net_investing': fmt(net_investing),
            'finance_equity': fmt(fin_equity),
            'finance_retained': fmt(fin_retained),
            'finance_lt_liabilities': fmt(fin_lt_liab),
            'net_financing': fmt(net_financing),
            'net_change': fmt(net_change),
            'opening_cash': fmt(opening_cash),
            'closing_cash': fmt(closing_cash),
        }
        filters = rec._get_filter_data()
        return data, filters

    # ── filter ──────────────────────────────────────────────────────────────

    def filter(self, vals):
        filter_result = []
        today = fields.Date.today()

        date_presets = {
            'month': lambda: (get_month(today)[0], get_month(today)[1]),
            'quarter': lambda: (get_quarter(today)[0], get_quarter(today)[1]),
            'year': lambda: (get_fiscal_year(today)[0], get_fiscal_year(today)[1]),
            'last-month': lambda: (get_month(subtract(today, months=1))[0],
                                   get_month(subtract(today, months=1))[1]),
            'last-quarter': lambda: (get_quarter(subtract(today, months=3))[0],
                                     get_quarter(subtract(today, months=3))[1]),
            'last-year': lambda: (get_fiscal_year(subtract(today, years=1))[0],
                                  get_fiscal_year(subtract(today, years=1))[1]),
        }
        if isinstance(vals, str) and vals in date_presets:
            start, end = date_presets[vals]()
            vals = {
                'date_from': start.strftime('%Y-%m-%d'),
                'date_to': end.strftime('%Y-%m-%d'),
            }
        if isinstance(vals, dict):
            if 'date_from' in vals:
                self.write({'date_from': vals['date_from']})
            if 'date_to' in vals:
                self.write({'date_to': vals['date_to']})
            if 'journal_ids' in vals:
                jid = int(vals['journal_ids'])
                if jid in self.journal_ids.ids:
                    self.update({'journal_ids': [(3, jid)]})
                else:
                    self.write({'journal_ids': [(4, jid)]})
                filter_result.append({'journal_ids': self.journal_ids.mapped('code')})
            if 'target' in vals:
                self.write({'target_move': vals['target']})
                filter_result.append({'target_move': self.target_move})
        return filter_result

    def _get_filter_data(self):
        journals = self.env['account.journal'].search([])
        return {
            'journal': [{'id': j.id, 'name': j.name} for j in journals],
        }

    # ── XLSX export ─────────────────────────────────────────────────────────

    @api.model
    def get_xlsx_report(self, data, response, report_name):
        data = json.loads(data)
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet()

        title_fmt = wb.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        section_fmt = wb.add_format({
            'bold': True, 'font_size': 10,
            'bg_color': '#2E75B6', 'font_color': 'white', 'border': 1})
        label_fmt = wb.add_format({'font_size': 10, 'border': 1, 'indent': 1})
        total_fmt = wb.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#D6E4F0', 'border': 1})
        amount_fmt = wb.add_format({
            'font_size': 10, 'border': 1,
            'num_format': '#,##0.00', 'align': 'right'})
        total_amt_fmt = wb.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#D6E4F0', 'border': 1,
            'num_format': '#,##0.00', 'align': 'right'})
        summary_lbl_fmt = wb.add_format({
            'bold': True, 'font_size': 11,
            'bg_color': '#1B4F72', 'font_color': 'white', 'border': 1})
        summary_amt_fmt = wb.add_format({
            'bold': True, 'font_size': 11,
            'bg_color': '#1B4F72', 'font_color': 'white', 'border': 1,
            'num_format': '#,##0.00', 'align': 'right'})

        ws.set_column(0, 0, 48)
        ws.set_column(1, 1, 20)

        def flt(s):
            try:
                return float(str(s).replace(',', ''))
            except Exception:
                return 0.0

        row = 0
        ws.merge_range(row, 0, row, 1, report_name, title_fmt)
        row += 2

        def write_section(title, items, total_label, total_key):
            nonlocal row
            ws.merge_range(row, 0, row, 1, title, section_fmt)
            row += 1
            for lbl, key in items:
                ws.write(row, 0, lbl, label_fmt)
                ws.write(row, 1, flt(data[key]), amount_fmt)
                row += 1
            ws.write(row, 0, total_label, total_fmt)
            ws.write(row, 1, flt(data[total_key]), total_amt_fmt)
            row += 2

        write_section(
            'A.  OPERATING ACTIVITIES',
            [
                ('Net Profit / (Loss)', 'net_income'),
                ('Add: Depreciation & Amortisation', 'depreciation'),
                ('(Increase)/Decrease in Trade Receivables', 'wc_receivables'),
                ('(Increase)/Decrease in Prepayments', 'wc_prepayments'),
                ('(Increase)/Decrease in Other Current Assets', 'wc_current_assets'),
                ('Increase/(Decrease) in Trade Payables', 'wc_payables'),
                ('Increase/(Decrease) in Credit Card Liabilities', 'wc_credit_card'),
                ('Increase/(Decrease) in Other Current Liabilities', 'wc_current_liabilities'),
            ],
            'Net Cash from Operating Activities',
            'net_operating',
        )
        write_section(
            'B.  INVESTING ACTIVITIES',
            [
                ('(Purchase)/Disposal of Fixed Assets', 'invest_fixed'),
                ('(Purchase)/Disposal of Non-current Assets', 'invest_non_current'),
            ],
            'Net Cash from Investing Activities',
            'net_investing',
        )
        write_section(
            'C.  FINANCING ACTIVITIES',
            [
                ('Proceeds from Share Issuance / Capital', 'finance_equity'),
                ('Change in Retained / Unallocated Earnings', 'finance_retained'),
                ('Proceeds from / (Repayment of) Long-term Borrowings', 'finance_lt_liabilities'),
            ],
            'Net Cash from Financing Activities',
            'net_financing',
        )

        ws.write(row, 0, 'NET INCREASE / (DECREASE) IN CASH', summary_lbl_fmt)
        ws.write(row, 1, flt(data['net_change']), summary_amt_fmt)
        row += 1
        ws.write(row, 0, 'Opening Cash and Cash Equivalents', label_fmt)
        ws.write(row, 1, flt(data['opening_cash']), amount_fmt)
        row += 1
        ws.write(row, 0, 'Closing Cash and Cash Equivalents', summary_lbl_fmt)
        ws.write(row, 1, flt(data['closing_cash']), summary_amt_fmt)

        wb.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
