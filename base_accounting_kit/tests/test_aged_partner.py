# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import tagged
from .common import AccountingKitCommon

AS_OF = '2026-06-30'


@tagged('post_install', '-at_install', 'accounting_kit')
class TestAgedPartnerBalance(AccountingKitCommon):
    """Figures on the Aged Partner Balance, as of 30 June 2026.

    Buckets: 'direction' is not yet due, '4' is 1-30 days overdue, '3' is
    31-60, '2' is 61-90, '1' is 91-120 and '0' is over 120.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_income = cls.env['account.account'].search(
            [('account_type', '=', 'income')], limit=1)
        cls.mama_mboga = cls.env['res.partner'].create({'name': 'Mama Mboga Traders'})
        cls.kariakor = cls.env['res.partner'].create({'name': 'Kariakor Spares'})

        cls._invoice(cls.mama_mboga, 10000, '2026-05-15')      # 46 days late
        cls._invoice(cls.mama_mboga, 5000, '2026-07-15')       # not yet due
        part_paid = cls._invoice(cls.mama_mboga, 8000, '2026-06-20')
        cls._pay(part_paid, 3000, '2026-06-25')                # 5,000 left, 10 days late
        paid = cls._invoice(cls.mama_mboga, 2000, '2026-06-01')
        cls._pay(paid, 2000, '2026-06-10')                     # settled before the date

        cls._invoice(cls.kariakor, 7000, '2026-01-01')         # 180 days late
        paid_later = cls._invoice(cls.kariakor, 4000, '2026-06-10')
        cls._pay(paid_later, 4000, '2026-07-05')               # still open on 30 June

    @classmethod
    def _invoice(cls, partner, amount, due):
        move = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': '2026-01-01',
            'invoice_date_due': due,
            'invoice_line_ids': [Command.create({
                'name': 'Goods',
                'quantity': 1,
                'price_unit': amount,
                'account_id': cls.account_income.id,
                'tax_ids': [Command.clear()],
            })],
        })
        move.action_post()
        return move

    @classmethod
    def _pay(cls, invoice, amount, date):
        cls.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'amount': amount, 'payment_date': date})._create_payments()

    def _report(self):
        report = self.env['report.base_accounting_kit.report_agedpartnerbalance']
        rows, totals, _lines = report._get_partner_move_lines(
            ['asset_receivable'], AS_OF, 'posted', 30)
        return {row['partner_id']: row for row in rows}, totals

    def test_open_amounts_land_in_the_right_buckets(self):
        rows, _totals = self._report()
        mboga = rows[self.mama_mboga.id]
        self.assertAlmostEqual(mboga['direction'], 5000.0, places=2)
        self.assertAlmostEqual(mboga['4'], 5000.0, places=2)
        self.assertAlmostEqual(mboga['3'], 10000.0, places=2)
        self.assertAlmostEqual(mboga['total'], 20000.0, places=2)

    def test_payment_after_the_report_date_does_not_reduce_the_balance(self):
        rows, _totals = self._report()
        kariakor = rows[self.kariakor.id]
        self.assertAlmostEqual(kariakor['0'], 7000.0, places=2)
        self.assertAlmostEqual(kariakor['4'], 4000.0, places=2)
        self.assertAlmostEqual(kariakor['total'], 11000.0, places=2)

    def test_grand_total_is_everything_still_owed(self):
        _rows, totals = self._report()
        # totals: [over 120, 91-120, 61-90, 31-60, 1-30, grand total, not due]
        self.assertAlmostEqual(totals[0], 7000.0, places=2)
        self.assertAlmostEqual(totals[3], 10000.0, places=2)
        self.assertAlmostEqual(totals[4], 9000.0, places=2)
        self.assertAlmostEqual(totals[6], 5000.0, places=2)
        self.assertAlmostEqual(totals[5], 31000.0, places=2)
