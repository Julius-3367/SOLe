from odoo import models


class InvoiceStatementReport(models.AbstractModel):
    _name = 'report.inv_statements_sce.inv_statement_pdf'
    _description = 'Invoice Statement PDF Report'

    def _get_report_values(self, docids, data=None):
        # report = self.env['ir.actions.report']._get_report_from_name(
        #     'base.report_irmodulereference')
        invoice_ids = {}
        bill_ids = {}
        invoice_total = {}
        bill_total = {}
        inv_residual = {}
        bill_residual = {}

        wizard_id = self.env['inv.statement.wiz'].browse(docids)
        partner_ids = wizard_id.partner_ids
        if not len(partner_ids):
            partner_ids = self.env['res.partner'].search([])

        for partner_id in partner_ids:
            invoice_ids[partner_id.id] = self.env['account.move'].search([
                ('partner_id', '=', partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted')])
            bill_ids[partner_id.id] = self.env['account.move'].search([
                ('partner_id', '=', partner_id.id),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted')])

            invoice_total[partner_id.id] = 0
            inv_residual[partner_id.id] = 0
            bill_total[partner_id.id] = 0
            bill_residual[partner_id.id] = 0
            for invoice_id in invoice_ids[partner_id.id]:
                invoice_total[partner_id.id] += invoice_id.amount_total
                inv_residual[partner_id.id] += invoice_id.amount_residual
            for bill_id in bill_ids[partner_id.id]:
                bill_total[partner_id.id] += bill_id.amount_total
                bill_residual[partner_id.id] += bill_id.amount_residual

        return {
            'doc_ids': docids,
            'doc_model': 'customer.statement.wiz',
            'company_id': wizard_id.company_id,
            'docs': partner_ids,
            'invoice_ids': invoice_ids,
            'bill_ids': bill_ids,
            'invoice_total': invoice_total,
            'bill_total': bill_total,
            'inv_residual': inv_residual,
            'bill_residual': bill_residual,
        }
