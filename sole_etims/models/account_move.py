# -*- coding: utf-8 -*-
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# KRA eTIMS VAT type codes
_VAT_TYPE = {16: 'A', 8: 'B'}  # 0% handled separately (C=zero-rated, E=exempt)


class AccountMove(models.Model):
    _inherit = 'account.move'

    sole_etims_show_button = fields.Boolean(
        string='Show Send to eTIMS',
        compute='_compute_sole_etims_show_button',
    )

    @api.depends('country_code', 'l10n_ke_cu_qrcode', 'state', 'move_type',
                 'company_id', 'company_id.sole_etims_enabled')
    def _compute_sole_etims_show_button(self):
        for move in self:
            move.sole_etims_show_button = (
                move.country_code == 'KE'
                and not move.l10n_ke_cu_qrcode
                and move.state == 'posted'
                and move.move_type in ('out_invoice', 'out_refund')
                and move.company_id.sole_etims_enabled
            )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _sole_etims_vat_type(self, tax):
        """Return KRA eTIMS VAT type code for a given tax record.

        A = 16% standard rate
        B = 8% reduced rate (e.g. fuel, LPG)
        C = zero-rated supply (l10n_ke_item_code tax_rate = 'C')
        E = exempt supply (l10n_ke_item_code tax_rate = 'E')
        """
        if not tax:
            return 'A'
        code = _VAT_TYPE.get(int(tax.amount))
        if code:
            return code
        if tax.amount == 0:
            item_code = getattr(tax, 'l10n_ke_item_code_id', None)
            if item_code:
                return item_code.tax_rate or 'C'
            return 'C'
        return 'A'

    def _sole_etims_build_payload(self):
        """Serialise this invoice to the KRA eTIMS VSCU JSON schema."""
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id
        inv_date = self.invoice_date or fields.Date.today()
        now = datetime.now()

        # Sequential number required by KRA (auto-increment, never repeated)
        invc_no = int(
            self.env['ir.sequence'].next_by_code('sole.etims.invoice') or 1
        )

        rcpt_type = 'R' if self.move_type == 'out_refund' else 'S'
        org_invc_no = 0
        if self.move_type == 'out_refund' and self.reversed_entry_id:
            try:
                org_invc_no = int(self.reversed_entry_id.l10n_ke_cu_invoice_number or 0)
            except (ValueError, TypeError):
                org_invc_no = 0

        # Per-VAT-type accumulators
        totals = {t: {'taxable': 0.0, 'tax': 0.0} for t in ('A', 'B', 'C', 'D', 'E')}
        item_list = []

        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.quantity
        )
        for seq, line in enumerate(product_lines, start=1):
            # Pick the first VAT-type tax on the line
            vat_tax = next(
                (t for t in line.tax_ids if t.amount in (16, 8, 0)),
                None,
            )
            vat_type = self._sole_etims_vat_type(vat_tax)
            taxable = abs(float(line.price_subtotal))
            tax_amt = abs(float(line.price_total)) - taxable
            total_line = taxable + tax_amt

            totals[vat_type]['taxable'] += taxable
            totals[vat_type]['tax'] += tax_amt

            item_code = getattr(vat_tax, 'l10n_ke_item_code_id', None) if vat_tax else None
            uom_name = (line.product_uom_id.name or 'U')[:3].upper()
            item_list.append({
                'itemSeq': seq,
                'itemCd': item_code.code if item_code else '',
                'itemClsCd': item_code.code if item_code else '',
                'itemNm': (line.name or (line.product_id.name if line.product_id else '') or '')[:100],
                'bcd': None,
                'pkgUnitCd': 'BX',
                'pkg': abs(float(line.quantity)),
                'qtyUnitCd': uom_name,
                'qty': abs(float(line.quantity)),
                'prc': round(float(line.price_unit), 2),
                'splyAmt': round(taxable, 2),
                'dcRt': float(line.discount or 0),
                'dcAmt': round(
                    float(line.price_unit) * abs(float(line.quantity))
                    * float(line.discount or 0) / 100,
                    2,
                ),
                'isrccCd': None,
                'isrccNm': None,
                'isrcRt': None,
                'isrcAmt': None,
                'vatTyCd': vat_type,
                'exciseTxTyCd': None,
                'taxblAmt': round(taxable, 2),
                'taxAmt': round(tax_amt, 2),
                'totAmt': round(total_line, 2),
            })

        tot_taxable = sum(v['taxable'] for v in totals.values())
        tot_tax = sum(v['tax'] for v in totals.values())

        user = self.env.user
        return {
            'invcNo': invc_no,
            'orgInvcNo': org_invc_no,
            'cfmDt': now.strftime('%Y%m%d%H%M%S'),
            'salesDt': inv_date.strftime('%Y%m%d'),
            'stockRlsDt': None,
            'cnclReqDt': None,
            'cnclDt': None,
            'pmtTyCd': '03',
            'rcptTyCd': rcpt_type,
            'custTin': (partner.vat or '').strip() or None,
            'custBhfId': None,
            'custNm': partner.name or '',
            'adrs': ' '.join(filter(None, [partner.street, partner.city])),
            'dbtRsnCd': '',
            'invcDspo': None,
            'totItemCnt': len(item_list),
            'taxblAmtA': round(totals['A']['taxable'], 2),
            'taxblAmtB': round(totals['B']['taxable'], 2),
            'taxblAmtC': round(totals['C']['taxable'], 2),
            'taxblAmtD': round(totals['D']['taxable'], 2),
            'taxblAmtE': round(totals['E']['taxable'], 2),
            'taxRtA': 16.0,
            'taxRtB': 8.0,
            'taxRtC': 0.0,
            'taxRtD': 0.0,
            'taxRtE': 0.0,
            'taxAmtA': round(totals['A']['tax'], 2),
            'taxAmtB': round(totals['B']['tax'], 2),
            'taxAmtC': round(totals['C']['tax'], 2),
            'taxAmtD': round(totals['D']['tax'], 2),
            'taxAmtE': round(totals['E']['tax'], 2),
            'totTaxblAmt': round(tot_taxable, 2),
            'totTaxAmt': round(tot_tax, 2),
            'totAmt': round(tot_taxable + tot_tax, 2),
            'prchrAcptcYn': 'N',
            'remark': (self.narration or '')[:100],
            'regrId': user.login or '',
            'regrNm': user.name or '',
            'modrId': user.login or '',
            'modrNm': user.name or '',
            'itemList': item_list,
        }

    # -------------------------------------------------------------------------
    # Public action
    # -------------------------------------------------------------------------

    def action_send_to_etims(self):
        """POST this invoice to the KRA eTIMS VSCU API."""
        self.ensure_one()
        company = self.company_id

        if not company.sole_etims_enabled:
            raise UserError(_(
                "eTIMS is not enabled for this company. "
                "Go to Accounting > Configuration > Settings to configure it."
            ))
        if self.l10n_ke_cu_qrcode:
            raise UserError(_("This invoice has already been submitted to eTIMS."))

        errors = self._l10n_ke_validate_move()
        if errors:
            raise UserError('\n'.join(
                msg for _, msgs in errors for msg in msgs
            ))

        payload = self._sole_etims_build_payload()
        base_url = (company.sole_etims_api_url or '').rstrip('/')
        url = f"{base_url}/v1/trnsSales/saveTrnsSalesOsdc"

        headers = {
            'Content-Type': 'application/json',
            'tin': company.vat or '',
            'bhfId': company.sole_etims_branch_id or '00',
            'cmcKey': company.sole_etims_cmc_key or '',
        }
        _logger.info("sole_etims: submitting invoice %s to %s", self.name, url)

        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=req_data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            _logger.error("sole_etims: HTTP %s from KRA API: %s", exc.code, body)
            raise UserError(_("KRA eTIMS API returned HTTP %s: %s") % (exc.code, body))
        except urllib.error.URLError as exc:
            raise UserError(_("Cannot reach eTIMS API at %s: %s") % (url, exc.reason))
        except Exception as exc:
            raise UserError(_("eTIMS submission failed: %s") % exc)

        result_code = result.get('resultCd', '')
        if result_code != '000':
            raise UserError(_(
                "KRA rejected the invoice (code %(code)s): %(msg)s"
            ) % {'code': result_code, 'msg': result.get('resultMsg', '')})

        data = result.get('data', {})
        date_str = data.get('vsdcRcptPbctDate') or datetime.now().strftime('%Y%m%d%H%M%S')
        try:
            cu_datetime = datetime.strptime(date_str, '%Y%m%d%H%M%S')
        except ValueError:
            cu_datetime = datetime.now()

        self.write({
            'l10n_ke_cu_invoice_number': str(data.get('rcptNo', '')),
            'l10n_ke_cu_serial_number': data.get('sdcId') or company.sole_etims_device_serial or '',
            'l10n_ke_cu_qrcode': data.get('qrCode') or data.get('mrcNo', ''),
            'l10n_ke_cu_datetime': cu_datetime,
        })
        _logger.info(
            "sole_etims: invoice %s submitted, KRA receipt no %s",
            self.name, data.get('rcptNo'),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sent to eTIMS'),
                'message': _(
                    'Invoice %(name)s submitted to KRA. Receipt No: %(no)s'
                ) % {'name': self.name, 'no': data.get('rcptNo', '')},
                'type': 'success',
                'sticky': False,
            },
        }
