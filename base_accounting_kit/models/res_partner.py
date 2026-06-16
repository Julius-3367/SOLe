# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    invoice_list = fields.One2many('account.move', 'partner_id',
                                   string="Invoice Details",
                                   readonly=True,
                                   domain=[('payment_state', '=', 'not_paid'),
                                           ('move_type', '=', 'out_invoice')])
    total_due = fields.Monetary(compute='_compute_for_followup', store=False, readonly=True)
    next_reminder_date = fields.Date(compute='_compute_for_followup', store=False, readonly=True)
    total_overdue = fields.Monetary(compute='_compute_for_followup', store=False, readonly=True)
    followup_status = fields.Selection(
        [('in_need_of_action', 'In need of action'),
         ('with_overdue_invoices', 'With overdue invoices'),
         ('no_action_needed', 'No action needed')],
        string='Followup status',
    )
    followup_reminder_sent = fields.Date(string='Last Reminder Sent', readonly=True)

    def _compute_for_followup(self):
        for record in self:
            total_due = 0
            total_overdue = 0
            today = fields.Date.today()
            for am in record.invoice_list:
                if am.company_id == self.env.company:
                    amount = am.amount_residual
                    total_due += amount
                    is_overdue = today > am.invoice_date_due if am.invoice_date_due else today > am.date
                    if is_overdue:
                        total_overdue += amount or 0
            min_date = record.get_min_date()
            action = record.action_after()
            if min_date:
                date_reminder = min_date + timedelta(days=action)
                record.next_reminder_date = date_reminder
            else:
                date_reminder = today
                record.next_reminder_date = date_reminder
            if total_overdue > 0 and date_reminder > today:
                followup_status = "with_overdue_invoices"
            elif total_due > 0 and date_reminder <= today:
                followup_status = "in_need_of_action"
            else:
                followup_status = "no_action_needed"
            record.total_due = total_due
            record.total_overdue = total_overdue
            record.followup_status = followup_status

    def get_min_date(self):
        today = date.today()
        for this in self:
            if this.invoice_list:
                min_list = [d for d in this.invoice_list.mapped('invoice_date_due') if d]
                return min(min_list) if min_list else today
            return today

    def get_delay(self):
        delay = """SELECT id, delay FROM followup_line WHERE followup_id =
        (SELECT id FROM account_followup WHERE company_id = %s)
         ORDER BY delay LIMIT 1"""
        self.env.cr.execute(delay, [self.env.company.id])
        return self.env.cr.dictfetchall()

    def action_after(self):
        lines = self.env['followup.line'].search([
            ('followup_id.company_id', '=', self.env.company.id)])
        if lines:
            record = self.get_delay()
            for i in record:
                return i['delay']
        return 0

    def action_send_followup_email(self):
        """Send a follow-up reminder email to the customer."""
        self.ensure_one()
        if not self.email:
            raise UserError(_("Customer %s has no email address configured.") % self.name)
        template = self.env.ref(
            'base_accounting_kit.mail_template_followup_reminder',
            raise_if_not_found=False)
        if not template:
            raise UserError(_("Follow-up email template not found. Please reinstall base_accounting_kit."))
        template.send_mail(self.id, force_send=True)
        self.followup_reminder_sent = fields.Date.today()
        self.message_post(
            body=_("Follow-up reminder email sent to %s") % self.email,
            subtype_xmlid='mail.mt_note',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reminder Sent'),
                'message': _('Follow-up email sent to %s') % self.email,
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_send_followup_reminders(self):
        """Cron: send follow-up reminders to all partners in 'in_need_of_action' status."""
        partners = self.search([('customer_rank', '>', 0)])
        partners._compute_for_followup()
        for partner in partners:
            if partner.followup_status == 'in_need_of_action' and partner.email:
                last_sent = partner.followup_reminder_sent
                if not last_sent or (fields.Date.today() - last_sent).days >= 7:
                    try:
                        partner.action_send_followup_email()
                    except Exception:
                        pass
