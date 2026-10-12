# -*- coding: utf-8 -*-
from odoo import _, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def action_payslip_done(self):
        res = super().action_payslip_done()
        Request = self.env["sole.staff.request"]
        for slip in self.filtered(lambda s: s.state == "done" and not s.credit_note):
            if not any(line.code == "STAFF_ADVANCE" and line.total for line in slip.line_ids):
                continue
            requests = Request._advances_to_recover(slip.employee_id, slip.date_to)
            requests._workflow_write({"recovered_payslip_id": slip.id})
            for request in requests:
                request.message_post(body=_("Recovered through payslip %s.") % (slip.number or slip.name))
        return res

    def action_payslip_cancel(self):
        requests = self.env["sole.staff.request"].sudo().search([("recovered_payslip_id", "in", self.ids)])
        if requests:
            requests._workflow_write({"recovered_payslip_id": False})
            for request in requests:
                request.message_post(body=_("Payslip cancelled; the advance is to be recovered again."))
        return super().action_payslip_cancel()
