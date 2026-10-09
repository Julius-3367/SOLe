# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestFiscalDevice(AccountTestInvoicingCommon):
    """A Kenyan invoice with no fiscal device details is, by default, warned
    about and emailed as a proforma. A company that fiscalises by hand on a
    stand-alone device says so, and gets its real invoices sent."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('ke')
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice = cls.init_invoice('out_invoice', amounts=[15080], post=True)
        cls.Send = cls.env['account.move.send']

    def _pdf_errors(self):
        invoice_data = self.Send._get_default_sending_settings(self.invoice)   # what the Send wizard uses
        self.Send._hook_invoice_document_before_pdf_report_render(self.invoice, invoice_data)
        return invoice_data.get('error')

    def test_by_default_an_unfiscalised_invoice_is_warned_about(self):
        self.assertFalse(self.invoice._l10n_ke_fiscal_device_details_filled())
        self.assertEqual(self.Send._get_l10n_ke_edi_tremol_warning_moves(self.invoice), self.invoice)
        self.assertTrue(self._pdf_errors(), "without device details the invoice goes out as a proforma")

    def test_fiscalised_on_a_separate_device_sends_the_real_invoice(self):
        self.env.company.sole_fiscal_device_manual = True
        self.assertTrue(self.invoice._l10n_ke_fiscal_device_details_filled())
        self.assertFalse(self.Send._get_l10n_ke_edi_tremol_warning_moves(self.invoice))
        self.assertFalse(self._pdf_errors())

    def test_the_setting_is_per_company(self):
        self.env.company.sole_fiscal_device_manual = True
        other = self.setup_other_company()['company']
        self.assertFalse(other.sole_fiscal_device_manual)
