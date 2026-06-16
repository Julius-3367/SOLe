# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sole_etims_enabled = fields.Boolean(
        string='Enable eTIMS (VSCU)',
        help='Use KRA eTIMS VSCU API instead of the Tremol hardware device.',
    )
    sole_etims_api_url = fields.Char(
        string='eTIMS API Base URL',
        default='https://etims-sbx.kra.go.ke/etims-api',
        help='KRA eTIMS API base URL. Use the sandbox URL for testing.',
    )
    sole_etims_branch_id = fields.Char(
        string='Branch ID (bhfId)',
        default='00',
        help='Two-character KRA branch identifier, e.g. "00" for headquarters.',
    )
    sole_etims_cmc_key = fields.Char(
        string='Communication Key (cmcKey)',
        help='Communication key issued by KRA during VSCU device registration.',
    )
    sole_etims_device_serial = fields.Char(
        string='Device Serial Number',
        help='Serial number assigned by KRA to this VSCU device.',
    )

    def _compute_l10n_ke_oscu_is_active(self):
        """Mark OSCU active when eTIMS VSCU is configured — hides the Tremol button."""
        for company in self:
            company.l10n_ke_oscu_is_active = bool(company.sole_etims_enabled)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sole_etims_enabled = fields.Boolean(
        related='company_id.sole_etims_enabled',
        readonly=False,
        string='Enable KRA eTIMS (VSCU)',
    )
    sole_etims_api_url = fields.Char(
        related='company_id.sole_etims_api_url',
        readonly=False,
        string='eTIMS API URL',
    )
    sole_etims_branch_id = fields.Char(
        related='company_id.sole_etims_branch_id',
        readonly=False,
        string='Branch ID',
    )
    sole_etims_cmc_key = fields.Char(
        related='company_id.sole_etims_cmc_key',
        readonly=False,
        string='Communication Key',
    )
    sole_etims_device_serial = fields.Char(
        related='company_id.sole_etims_device_serial',
        readonly=False,
        string='Device Serial No.',
    )
