# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Set the main company up for the Kenyan market.

    A fresh SOLe install starts on Odoo's generic chart of accounts
    (US/USD), which leaves the Kenyan VAT/withholding-tax templates
    unusable (Odoo only offers taxes whose country matches the
    company's fiscal country). On first install — i.e. before any
    journal entry exists — point the company at Kenya/KES and load
    the official KRA-aligned chart of accounts from l10n_ke so VAT,
    withholding tax and statutory tax reports work out of the box.
    """
    company = env.company
    kenya = env.ref('base.ke')
    kes = env.ref('base.KES')
    kes.sudo().active = True

    if company.root_id._existing_accounting():
        _logger.warning(
            "sole_kenya: company '%s' already has journal entries — "
            "leaving its chart of accounts and currency untouched. "
            "Set country/currency and load the Kenya chart manually "
            "via Accounting > Configuration if this should be a Kenyan company.",
            company.name,
        )
        if not company.country_id:
            company.country_id = kenya
        return

    company.write({
        'country_id': kenya.id,
        'currency_id': kes.id,
    })
    env['account.chart.template'].try_loading('ke', company=company)
