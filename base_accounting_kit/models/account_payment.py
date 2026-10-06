# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountRegisterPayments(models.TransientModel):
    """Inherits the account.payment.register model to add the new
     fields and functions"""
    _inherit = "account.payment.register"

    bank_reference = fields.Char(string="Bank Reference", copy=False)
    cheque_reference = fields.Char(string="Cheque Reference", copy=False)
    effective_date = fields.Date('Effective Date',
                                 help='Effective date of PDC', copy=False,
                                 default=False)

    def _prepare_payment_vals(self, invoices):
        """Its prepare the payment values for the invoice and update
         the MultiPayment"""
        res = super(AccountRegisterPayments, self)._prepare_payment_vals(
            invoices)
        # Check payment method is Check or PDC
        check_pdc_ids = self.env['account.payment.method'].search(
            [('code', 'in', ['pdc', 'check_printing'])])
        if self.payment_method_id.id in check_pdc_ids.ids:
            currency_id = self.env['res.currency'].browse(res['currency_id'])
            journal_id = self.env['account.journal'].browse(res['journal_id'])
            # Updating values in case of Multi payments
            res.update({
                'bank_reference': self.bank_reference,
                'cheque_reference': self.cheque_reference,
                'check_manual_sequencing': journal_id.check_manual_sequencing,
                'effective_date': self.effective_date,
                'check_amount_in_words': currency_id.amount_to_text(
                    res['amount']),
            })
        return res

    def _create_payment_vals_from_wizard(self, batch_result):
        """It super the wizard action of the create payment values and update
         the bank and cheque values"""
        res = super(AccountRegisterPayments,
                    self)._create_payment_vals_from_wizard(
            batch_result)
        if self.effective_date:
            res.update({
                'bank_reference': self.bank_reference,
                'cheque_reference': self.cheque_reference,
                'effective_date': self.effective_date,
            })
        return res

    def _create_payment_vals_from_batch(self, batch_result):
        """It super the batch action of the create payment values and update
         the bank and cheque values"""
        res = super(AccountRegisterPayments,
                    self)._create_payment_vals_from_batch(
            batch_result)
        if self.effective_date:
            res.update({
                'bank_reference': self.bank_reference,
                'cheque_reference': self.cheque_reference,
                'effective_date': self.effective_date,
            })
        return res

    def _create_payments(self):
        """USed to create a list of payments and update the bank and
         cheque reference"""
        payments = super(AccountRegisterPayments, self)._create_payments()

        for payment in payments:
            payment.write({
                'bank_reference': self.bank_reference,
                'cheque_reference': self.cheque_reference
            })
        return payments


class AccountPayment(models.Model):
    """"It inherits the account.payment model for adding new fields
     and functions"""
    _inherit = "account.payment"

    bank_reference = fields.Char(string="Bank Reference", copy=False)
    cheque_reference = fields.Char(string="Cheque Reference",copy=False)
    effective_date = fields.Date('Effective Date',
                                 help='Effective date of PDC', copy=False,
                                 default=False)

    def open_payment_matching_screen(self):
        """Open reconciliation view for customers/suppliers"""
        move_line_id = False
        for move_line in self.line_ids:
            if move_line.account_id.reconcile:
                move_line_id = move_line.id
                break
        if not self.partner_id:
            raise UserError(_("Payments without a customer can't be matched"))
        action_context = {'company_ids': [self.company_id.id], 'partner_ids': [
            self.partner_id.commercial_partner_id.id]}
        if self.partner_type == 'customer':
            action_context.update({'mode': 'customers'})
        elif self.partner_type == 'supplier':
            action_context.update({'mode': 'suppliers'})
        if move_line_id:
            action_context.update({'move_line_id': move_line_id})
        return {
            'type': 'ir.actions.client',
            'tag': 'manual_reconciliation_view',
            'context': action_context,
        }

    def _generate_move_vals(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        """Book a post-dated cheque on the date it can be banked.

        Cheque printing itself is left to account_check_printing; this module
        only adds the PDC method and its effective date.
        """
        vals = super()._generate_move_vals(write_off_line_vals, force_balance, line_ids)
        if self.payment_method_code == 'pdc' and self.effective_date:
            vals['date'] = self.effective_date
            for command in vals['line_ids']:
                command[2]['date_maturity'] = self.effective_date
        return vals


class AccountPaymentMethod(models.Model):
    """The class inherits the account payment method for supering the
    _get_payment_method_information function"""
    _inherit = "account.payment.method"

    @api.model
    def _get_payment_method_information(self):
        """Super the function to update the pdc values"""
        res = super()._get_payment_method_information()
        res['pdc'] = {'mode': 'multi', 'type': ('bank',)}
        return res
