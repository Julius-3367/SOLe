# -*- coding: utf-8 -*-
# Statement of Changes in Equity
# Part of SOLe Accounting Suite
import io
import json
import xlsxwriter
from odoo import api, fields, models
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter, subtract


class EquityStatementReport(models.TransientModel):
    """Statement of Changes in Equity.

    Columns:  Share Capital | Retained Earnings | Total Equity
    Rows:
      Opening Balance
      Net Income for the period
      Dividends / Drawings declared
      Other equity movements (share issues, transfers)
      Closing Balance
    """

    _name = 'equity.statement.report'
    _description = 'Statement of Changes in Equity'

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

    def _sum_aml(self, account_types, date_from=None, date_to=None, target_move=None):
        """Sum (debit - credit) for given account_types over a date range."""
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
        lines = self.env['account.move.line'].search(domain)
        return sum(lines.mapped('debit')) - sum(lines.mapped('credit'))

    # ── main report ─────────────────────────────────────────────────────────

    @api.model
    def view_report(self, option):
        rec = self.browse(option)
        tm = ['posted', 'draft'] if rec.target_move == 'draft' else ['posted']
        df, dt = rec.date_from, rec.date_to

        # ── OPENING BALANCES ─────────────────────────────────────────────────
        # equity accounts are credit-normal: net_db_cr negative = credit balance
        # balance = -net_db_cr (credit balance is positive equity)
        def open_bal(account_types):
            od = [
                ('parent_state', 'in', tm),
                ('account_id.account_type', 'in', account_types),
            ]
            if df:
                od.append(('date', '<', df))
            if rec.journal_ids:
                od.append(('journal_id', 'in', rec.journal_ids.ids))
            ls = self.env['account.move.line'].search(od)
            dbs = sum(ls.mapped('debit'))
            crs = sum(ls.mapped('credit'))
            return crs - dbs   # credit-normal → positive = credit balance

        open_share = open_bal(['equity'])
        open_retained = open_bal(['equity_unaffected'])
        open_total = open_share + open_retained

        # ── NET INCOME for the period ────────────────────────────────────────
        income_mv = rec._sum_aml(['income', 'income_other'], df, dt, tm)
        income = -(income_mv)   # credit-normal → negate for positive income

        expense_mv = rec._sum_aml(
            ['expense', 'expense_depreciation', 'expense_direct_cost'], df, dt, tm)
        expense = expense_mv  # debit-normal

        net_income = income - expense

        # ── EQUITY MOVEMENTS during period ───────────────────────────────────
        # Share capital changes (new shares, buybacks)
        share_mv_net = rec._sum_aml(['equity'], df, dt, tm)
        share_movement = -(share_mv_net)   # credit = increase in equity (positive)

        # Retained earnings movements (dividends, transfers)
        retained_mv_net = rec._sum_aml(['equity_unaffected'], df, dt, tm)
        retained_movement = -(retained_mv_net)

        # Dividends declared show as debit on equity accounts (reduce equity)
        # These are already captured in share_movement / retained_movement

        # ── CLOSING BALANCES ─────────────────────────────────────────────────
        close_share = open_share + share_movement
        close_retained = open_retained + retained_movement + net_income
        close_total = close_share + close_retained

        def fmt(v):
            return "{:,.2f}".format(v)

        data = {
            # Opening
            'open_share': fmt(open_share),
            'open_retained': fmt(open_retained),
            'open_total': fmt(open_total),
            # Net income
            'net_income_share': fmt(0.0),
            'net_income_retained': fmt(net_income),
            'net_income_total': fmt(net_income),
            # Share capital movements
            'share_movement': fmt(share_movement),
            'share_movement_retained': fmt(0.0),
            'share_movement_total': fmt(share_movement),
            # Retained / Other equity movements
            'retained_movement': fmt(0.0),
            'retained_movement_retained': fmt(retained_movement),
            'retained_movement_total': fmt(retained_movement),
            # Closing
            'close_share': fmt(close_share),
            'close_retained': fmt(close_retained),
            'close_total': fmt(close_total),
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
        header_fmt = wb.add_format({
            'bold': True, 'font_size': 10,
            'bg_color': '#2E75B6', 'font_color': 'white',
            'border': 1, 'align': 'center'})
        label_fmt = wb.add_format({'font_size': 10, 'border': 1, 'indent': 1})
        total_fmt = wb.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#D6E4F0', 'border': 1})
        amount_fmt = wb.add_format({
            'font_size': 10, 'border': 1,
            'num_format': '#,##0.00', 'align': 'right'})
        total_amt_fmt = wb.add_format({
            'bold': True, 'font_size': 10, 'bg_color': '#D6E4F0', 'border': 1,
            'num_format': '#,##0.00', 'align': 'right'})

        ws.set_column(0, 0, 40)
        ws.set_column(1, 3, 20)

        def flt(s):
            try:
                return float(str(s).replace(',', ''))
            except Exception:
                return 0.0

        row = 0
        ws.merge_range(row, 0, row, 3, report_name, title_fmt)
        row += 2

        # Column headers
        ws.write(row, 0, 'Description', header_fmt)
        ws.write(row, 1, 'Share Capital', header_fmt)
        ws.write(row, 2, 'Retained Earnings', header_fmt)
        ws.write(row, 3, 'Total Equity', header_fmt)
        row += 1

        def write_row(lbl, sc_key, re_key, tot_key, is_total=False):
            nonlocal row
            lf = total_fmt if is_total else label_fmt
            af = total_amt_fmt if is_total else amount_fmt
            ws.write(row, 0, lbl, lf)
            ws.write(row, 1, flt(data[sc_key]), af)
            ws.write(row, 2, flt(data[re_key]), af)
            ws.write(row, 3, flt(data[tot_key]), af)
            row += 1

        write_row('Opening Balance', 'open_share', 'open_retained', 'open_total', is_total=True)
        write_row('Net Income / (Loss) for Period',
                  'net_income_share', 'net_income_retained', 'net_income_total')
        write_row('Share Capital Movements',
                  'share_movement', 'share_movement_retained', 'share_movement_total')
        write_row('Other Equity Movements',
                  'retained_movement', 'retained_movement_retained', 'retained_movement_total')
        write_row('Closing Balance', 'close_share', 'close_retained', 'close_total', is_total=True)

        wb.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
