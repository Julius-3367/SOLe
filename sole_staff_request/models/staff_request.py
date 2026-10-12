# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

# Only the workflow methods may set these; a requester editing them over RPC
# could otherwise approve or "pay" their own request.
WORKFLOW_FIELDS = {
    "state", "approver_id", "approved_date", "rejection_reason", "journal_id",
    "payment_date", "payment_reference", "move_id", "paid_by_id",
    "recovered_payslip_id",
}
# Frozen once the request leaves draft, so what was approved is what gets paid
REQUEST_FIELDS = {
    "employee_id", "type_id", "amount", "purpose", "date_needed",
    "company_id", "recover_via_payroll", "recovery_date",
}


class SoleStaffRequest(models.Model):
    _name = "sole.staff.request"
    _description = "Staff Money Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Reference", default=lambda self: _("New"),
        readonly=True, copy=False, index=True,
    )
    employee_id = fields.Many2one(
        "hr.employee", required=True, tracking=True, check_company=True,
        default=lambda self: self.env.user.employee_id,
    )
    user_id = fields.Many2one(related="employee_id.user_id", store=True, string="Requester")
    department_id = fields.Many2one(related="employee_id.department_id", store=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")

    type_id = fields.Many2one(
        "sole.staff.request.type", string="Type", required=True,
        tracking=True, check_company=True,
    )
    type_description = fields.Text(related="type_id.description")
    amount = fields.Monetary(required=True, tracking=True)
    date_needed = fields.Date(default=fields.Date.context_today, tracking=True)
    purpose = fields.Text(
        string="Reason", required=True,
        help="What the money is for, e.g. 'Fare to Kiwool Advocates, Upper Hill, "
             "to install their new mail server'.",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Waiting Approval"),
            ("approved", "Approved"),
            ("paid", "Paid"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        default="draft", required=True, tracking=True, copy=False, index=True,
    )
    approver_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)
    approved_date = fields.Datetime(readonly=True, copy=False)
    rejection_reason = fields.Text(readonly=True, copy=False, tracking=True)

    journal_id = fields.Many2one("account.journal", string="Paid From", readonly=True, copy=False)
    payment_date = fields.Date(readonly=True, copy=False)
    payment_reference = fields.Char(
        readonly=True, copy=False, help="M-Pesa code, cheque or bank reference.")
    move_id = fields.Many2one("account.move", string="Journal Entry", readonly=True, copy=False)
    paid_by_id = fields.Many2one("res.users", readonly=True, copy=False)

    recover_via_payroll = fields.Boolean(
        tracking=True, copy=False,
        help="Deduct this amount from the employee's payslip.",
    )
    recovery_date = fields.Date(
        string="Recover from Payslip of", copy=False,
        help="The deduction is made on the first payslip ending on or after this date.",
    )
    recovered_payslip_id = fields.Many2one("hr.payslip", readonly=True, copy=False)
    recovery_status = fields.Selection(
        [("none", "Not Recovered"), ("pending", "To Recover"), ("done", "Recovered")],
        compute="_compute_recovery_status", store=True,
    )

    can_approve = fields.Boolean(compute="_compute_permissions")
    can_pay = fields.Boolean(compute="_compute_permissions")
    is_requester = fields.Boolean(compute="_compute_permissions")

    @api.onchange("type_id")
    def _onchange_type_id(self):
        self.recover_via_payroll = self.type_id.recover_via_payroll

    @api.depends("recover_via_payroll", "state", "recovered_payslip_id")
    def _compute_recovery_status(self):
        for request in self:
            if not request.recover_via_payroll or request.state != "paid":
                request.recovery_status = "none"
            elif request.recovered_payslip_id:
                request.recovery_status = "done"
            else:
                request.recovery_status = "pending"

    @api.depends_context("uid")
    @api.depends("approver_id", "user_id", "state")
    def _compute_permissions(self):
        user = self.env.user
        is_admin = user.has_group("sole_staff_request.group_staff_request_manager")
        is_finance = user.has_group("sole_staff_request.group_staff_request_finance")
        for request in self:
            own = request.user_id == user
            request.is_requester = own
            request.can_approve = request.state == "submitted" and not own and (
                request.approver_id == user or is_admin)
            request.can_pay = request.state == "approved" and is_finance

    @api.constrains("amount")
    def _check_amount(self):
        for request in self:
            if request.amount <= 0:
                raise ValidationError(_("The amount must be more than zero."))

    # ── CRUD guards ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if not self._workflow_allowed():
            for vals in vals_list:
                if WORKFLOW_FIELDS & set(vals) - {"state"} or vals.get("state", "draft") != "draft":
                    raise UserError(_("A request starts as a draft and follows the approval steps."))
        Type = self.env["sole.staff.request.type"]
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("sole.staff.request") or _("New")
            if "recover_via_payroll" not in vals and vals.get("type_id"):
                vals["recover_via_payroll"] = Type.browse(vals["type_id"]).recover_via_payroll
        return super().create(vals_list)

    def write(self, vals):
        if not self._workflow_allowed():
            if WORKFLOW_FIELDS & set(vals):
                raise UserError(_("Use the buttons on the request to approve, reject or pay it."))
            if REQUEST_FIELDS & set(vals) and any(r.state != "draft" for r in self):
                raise UserError(_(
                    "%s has already been submitted. Cancel it and reset it to "
                    "draft to change it.") % ", ".join(self.filtered(lambda r: r.state != "draft").mapped("name")))
        return super().write(vals)

    def unlink(self):
        if any(r.state not in ("draft", "cancelled") for r in self):
            raise UserError(_("Only draft or cancelled requests can be deleted."))
        if not self._workflow_allowed() and any(r.user_id != self.env.user for r in self):
            raise UserError(_("Only the requester can delete a request."))
        return super().unlink()

    def _workflow_allowed(self):
        return (
            self.env.context.get("sole_request_workflow")
            or self.env.su
            or self.env.user.has_group("sole_staff_request.group_staff_request_manager")
        )

    def _workflow_write(self, vals):
        return self.with_context(sole_request_workflow=True).write(vals)

    # ── Workflow ─────────────────────────────────────────────────────────────
    def _find_approver(self):
        self.ensure_one()
        requester = self.user_id
        approver = self.employee_id.parent_id.user_id
        if not approver or approver == requester:
            approver = self.company_id.sole_request_default_approver_id
        if not approver or approver == requester:
            raise UserError(_(
                "Nobody can approve %(name)s: %(employee)s has no manager on their "
                "employee record and no default approver is set in Staff Requests "
                "settings.", name=self.name, employee=self.employee_id.name))
        return approver

    def _notify_requester(self, body):
        for request in self:
            partner = request.user_id.partner_id or request.employee_id.work_contact_id
            request.message_post(
                body=body,
                partner_ids=partner.ids,
                subtype_xmlid="mail.mt_comment",
            )

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("%s is not a draft.") % request.name)
            if not (request.is_requester or request._workflow_allowed()):
                raise UserError(_("Only %s can submit this request.") % request.employee_id.name)
            limit = request.type_id.max_amount
            if limit and request.amount > limit:
                raise UserError(_(
                    "%(type)s requests are limited to %(limit)s.",
                    type=request.type_id.name,
                    limit=request.currency_id.format(limit)))
            approver = request._find_approver()
            request._workflow_write({"state": "submitted", "approver_id": approver.id})
            request.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=approver.id,
                summary=_("Approve %(name)s: %(amount)s", name=request.name,
                          amount=request.currency_id.format(request.amount)),
                note=request.purpose,
            )
        return True

    def action_approve(self):
        for request in self:
            if not request.can_approve:
                raise UserError(_("You cannot approve %s.") % request.name)
            request._workflow_write({"state": "approved", "approved_date": fields.Datetime.now()})
            request.activity_feedback(["mail.mail_activity_data_todo"], feedback=_("Approved"))
            finance = request.company_id.sole_request_finance_user_id
            if finance:
                request.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=finance.id,
                    summary=_("Pay %(name)s: %(amount)s", name=request.name,
                              amount=request.currency_id.format(request.amount)),
                )
            request._notify_requester(_("Your request %(name)s for %(amount)s was approved by %(user)s.",
                                        name=request.name,
                                        amount=request.currency_id.format(request.amount),
                                        user=self.env.user.name))
        return True

    def _do_reject(self, reason):
        if not (reason or "").strip():
            raise UserError(_("Give a reason so the requester knows why."))
        for request in self:
            if not request.can_approve:
                raise UserError(_("You cannot reject %s.") % request.name)
            request._workflow_write({"state": "rejected", "rejection_reason": reason.strip()})
            request.activity_unlink(["mail.mail_activity_data_todo"])
            request._notify_requester(_("Your request %(name)s was rejected by %(user)s. Reason: %(reason)s",
                                        name=request.name, user=self.env.user.name, reason=reason.strip()))
        return True

    def _do_pay(self, journal, payment_date, reference, recover, recovery_date):
        self.ensure_one()
        if not self.can_pay:
            raise UserError(_("%s cannot be paid by you, or is not approved.") % self.name)
        if recover:
            debit_account = self.company_id.sole_staff_advance_account_id
            if not debit_account:
                raise UserError(_("Set a Staff Advances Account in Staff Requests settings "
                                  "before paying a request that will be recovered through payroll."))
            if not recovery_date:
                raise UserError(_("Choose the payslip month the advance will be recovered from."))
        else:
            debit_account = self.type_id.expense_account_id
            if not debit_account:
                raise UserError(_("Set an expense account on the request type '%s'.") % self.type_id.name)
        credit_account = journal.default_account_id
        if not credit_account:
            raise UserError(_("The journal %s has no default account.") % journal.name)

        partner = self.employee_id.work_contact_id
        first_line = next(iter((self.purpose or "").strip().splitlines()), "")
        label = "%s: %s" % (self.name, first_line[:80])
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": payment_date,
            "ref": " ".join(filter(None, [self.name, reference])),
            "company_id": self.company_id.id,
            "line_ids": [
                Command.create({"name": label, "account_id": debit_account.id,
                                "partner_id": partner.id, "debit": self.amount}),
                Command.create({"name": label, "account_id": credit_account.id,
                                "partner_id": partner.id, "credit": self.amount}),
            ],
        })
        move.action_post()
        self._workflow_write({
            "state": "paid",
            "journal_id": journal.id,
            "payment_date": payment_date,
            "payment_reference": reference,
            "move_id": move.id,
            "paid_by_id": self.env.uid,
            "recover_via_payroll": recover,
            "recovery_date": recovery_date if recover else False,
        })
        self.activity_feedback(["mail.mail_activity_data_todo"], feedback=_("Paid"))
        body = _("Your request %(name)s for %(amount)s was paid from %(journal)s.",
                 name=self.name, amount=self.currency_id.format(self.amount), journal=journal.name)
        if reference:
            body = _("%(body)s Reference: %(ref)s.", body=body, ref=reference)
        if recover:
            body = _("%(body)s It will be deducted from your payslip from %(date)s.",
                     body=body, date=fields.Date.to_string(recovery_date))
        self._notify_requester(body)
        return move

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject %s") % self.name,
            "res_model": "sole.staff.request.reject",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_open_pay_wizard(self):
        self.ensure_one()
        if not self.can_pay:
            raise UserError(_("Only finance can pay an approved request."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Pay %s") % self.name,
            "res_model": "sole.staff.request.pay",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_cancel(self):
        for request in self:
            if request.state not in ("draft", "submitted", "approved"):
                raise UserError(_("%s can no longer be cancelled.") % request.name)
            if not (request.is_requester or request._workflow_allowed()):
                raise UserError(_("Only the requester can cancel %s.") % request.name)
            request._workflow_write({"state": "cancelled"})
            request.activity_unlink(["mail.mail_activity_data_todo"])
        return True

    def action_reset_draft(self):
        for request in self:
            if request.state not in ("rejected", "cancelled"):
                raise UserError(_("Only rejected or cancelled requests go back to draft."))
            if not (request.is_requester or request._workflow_allowed()):
                raise UserError(_("Only the requester can reopen %s.") % request.name)
            request._workflow_write({"state": "draft", "approver_id": False, "rejection_reason": False})
        return True

    def action_view_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
        }

    # ── Payroll recovery ─────────────────────────────────────────────────────
    @api.model
    def _advances_to_recover(self, employee, date_to):
        return self.sudo().search([
            ("employee_id", "=", employee.id),
            ("state", "=", "paid"),
            ("recover_via_payroll", "=", True),
            ("recovered_payslip_id", "=", False),
            ("recovery_date", "<=", date_to),
        ])
