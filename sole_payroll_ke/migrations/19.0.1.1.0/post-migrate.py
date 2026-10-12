# -*- coding: utf-8 -*-
"""Bring the salary rules up to date and move payroll terms onto hr.version.

The rules and the structure are loaded noupdate, which normally protects an
accountant's edits, and an ordinary upgrade skips them. In this release every
rule that read the contract was failing, so the shipped versions are reloaded
in 'init' mode, which writes them regardless. They stay noupdate afterwards.

Anything entered before this release went onto hr.contract, which the salary
rules never read. Copy it to the employee's current version where the version
has nothing yet, and give versions with a wage the Kenyan structure if they
have none. Values already on a version are left alone.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import convert_file

_logger = logging.getLogger(__name__)

RELOAD = ["data/salary_rules.xml", "data/payroll_structure.xml"]

KE_FIELDS = [
    "ke_food_allowance", "ke_airtime_allowance", "ke_pension_allowance",
    "ke_commuter_allowance", "ke_housing_allowance_unit",
    "ke_housing_allowance_fixed", "ke_housing_allowance_percentage",
    "ke_pension_contribution", "ke_voluntary_medical_insurance",
    "ke_life_insurance", "ke_education", "ke_is_li_managed_by_employee",
    "ke_is_secondary",
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for filename in RELOAD:
        convert_file(env, "sole_payroll_ke", filename, {}, mode="init", noupdate=True)
    structure = env.ref("sole_payroll_ke.structure_ke", raise_if_not_found=False)

    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'hr_contract'")
    columns = {row[0] for row in cr.fetchall()}
    copyable = [f for f in KE_FIELDS if f in columns]
    copied = 0
    if copyable and "employee_id" in columns:
        cr.execute(
            "SELECT employee_id, wage, %s FROM hr_contract "
            "WHERE state = 'open' AND COALESCE(active, true) ORDER BY date_start" % ", ".join(copyable)
        )
        for row in cr.dictfetchall():
            employee = env["hr.employee"].browse(row["employee_id"]).exists()
            if not employee or not employee.version_id:
                continue
            target = employee.version_id
            vals = {f: row[f] for f in copyable if row[f] and not target[f]}
            if row.get("wage") and not target.wage:
                vals["wage"] = row["wage"]
            if vals:
                target.write(vals)
                copied += 1

    unassigned = env["hr.version"].search([("struct_id", "=", False), ("wage", ">", 0)])
    if structure and unassigned:
        unassigned.write({"struct_id": structure.id})
    _logger.info(
        "sole_payroll_ke: copied contract terms to %d versions, set the Kenyan structure on %d",
        copied, len(unassigned) if structure else 0,
    )
