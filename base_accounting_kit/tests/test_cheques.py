# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.tests import tagged
from .common import AccountingKitCommon


@tagged('post_install', '-at_install', 'accounting_kit')
class TestCheques(AccountingKitCommon):
    """Post-dated cheques (PDC) and Odoo's own cheque printing alongside them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', cls.company.id)], limit=1)
        cls.customer = cls.env['res.partner'].create({'name': 'Kariakor Spares'})
        cls.pdc_line = cls._method_line('pdc', 'inbound')
        cls.manual_line = cls._method_line('manual', 'inbound')

    @classmethod
    def _method_line(cls, code, direction):
        lines = cls.bank[f'{direction}_payment_method_line_ids']
        line = lines.filtered(lambda l: l.code == code)[:1]
        if not line:
            method = cls.env['account.payment.method'].search(
                [('code', '=', code), ('payment_type', '=', direction)], limit=1)
            line = cls.env['account.payment.method.line'].create({
                'payment_method_id': method.id, 'journal_id': cls.bank.id,
            })
        return line

    def _payment(self, method_line, **vals):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.customer.id,
            'amount': 15000.0,
            'date': '2026-07-01',
            'journal_id': self.bank.id,
            'payment_method_line_id': method_line.id,
            **vals,
        })
        payment.action_post()
        return payment

    def test_pdc_is_booked_on_its_effective_date(self):
        payment = self._payment(self.pdc_line, effective_date='2026-08-15')

        self.assertEqual(payment.move_id.date, date(2026, 8, 15))
        self.assertEqual(
            set(payment.move_id.line_ids.mapped('date_maturity')), {date(2026, 8, 15)})

    def test_effective_date_is_ignored_for_other_methods(self):
        payment = self._payment(self.manual_line, effective_date='2026-08-15')

        self.assertEqual(payment.move_id.date, date(2026, 7, 1))

    def test_register_payment_wizard_carries_the_effective_date(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': '2026-07-01',
            'invoice_line_ids': [Command.create({
                'name': 'Spares', 'quantity': 1, 'price_unit': 15000.0,
                'tax_ids': [Command.clear()],
            })],
        })
        invoice.action_post()

        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({
            'journal_id': self.bank.id,
            'payment_method_line_id': self.pdc_line.id,
            'payment_date': '2026-07-01',
            'effective_date': '2026-08-15',
            'cheque_reference': 'CHQ 000123',
        })._create_payments()

        self.assertEqual(payment.effective_date, date(2026, 8, 15))
        self.assertEqual(payment.cheque_reference, 'CHQ 000123')
        self.assertEqual(payment.move_id.date, date(2026, 8, 15))

    def test_payment_form_keeps_odoo_cheque_buttons(self):
        arch = self.env['account.payment'].get_view(view_type='form')['arch']
        for needed in ('action_void_check', 'name="effective_date"', 'name="cheque_reference"'):
            self.assertTrue(needed in arch, f"payment form is missing {needed}")

    def test_mark_and_unmark_as_sent(self):
        payment = self._payment(self.manual_line)

        payment.mark_as_sent()
        self.assertTrue(payment.is_sent)
        payment.unmark_as_sent()
        self.assertFalse(payment.is_sent)
