from odoo import models, fields


class InvStatementWiz(models.TransientModel):
    _name = "inv.statement.wiz"
    _description = "Customer Invoice Statement Wizard"

    partner_ids = fields.Many2many('res.partner', string='Customer/ Vendor')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    def action_print_pdf(self):
        return self.env.ref('inv_statements_sce.action_report_inv_statement_sce').report_action(self)
