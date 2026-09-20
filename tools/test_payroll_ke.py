# -*- coding: utf-8 -*-
"""Compute one Kenyan payslip and print every line.

Run against the TEST database only:

    docker exec -i sole_app odoo shell -d sole_test --no-http < tools/test_payroll_ke.py

This is a smoke test, not a proof of correctness. It answers "do the rules
execute and produce the arithmetic we expect for one simple case", which is
the first thing worth knowing and a long way short of the last. Before payroll
runs for real, process a full month for staff whose correct figures are
already known and reconcile every line.

Expected result for a 100,000 monthly wage in September 2026, no allowances,
no insurance, no other deductions:

    BASIC                 100,000.00
    GROSS                 100,000.00
    NSSF Tier I               540.00   6% of the first 9,000
    NSSF Tier II            5,460.00   6% of 9,000 to 100,000
    NSSF                    6,000.00
    AHL                     1,500.00   1.5% of basic
    SHIF                    2,750.00   2.75% of gross
    Taxable Pay            89,750.00   gross less NSSF, SHIF and AHL
    Income Tax             21,708.35   banded
    Personal Relief        -2,400.00
    PAYE                   19,308.35
    Total Deductions       29,558.35
    NET                    70,441.65

Any difference from those figures is a bug worth finding before anyone
is paid from this.
"""
from datetime import date

WAGE = 100000.0
DATE_FROM = date(2026, 9, 1)
DATE_TO = date(2026, 9, 30)

structure = env.ref("sole_payroll_ke.structure_ke")
print("Structure : %s (%d rules)" % (structure.name, len(structure.rule_ids)))
print("Parent    : %s" % (structure.parent_id.name or "none — correct"))
print("Parameters: %d" % env["sole.payroll.parameter"].search_count([]))

# A throwaway employee, so the test never depends on real staff data.
employee = env["hr.employee"].search([("name", "=", "ZZ Payroll Test")], limit=1)
if not employee:
    employee = env["hr.employee"].create({"name": "ZZ Payroll Test"})

contract = env["hr.contract"].search([("employee_id", "=", employee.id)], limit=1)
if not contract:
    contract = env["hr.contract"].create({
        "name": "ZZ Payroll Test contract",
        "employee_id": employee.id,
        "wage": WAGE,
        "struct_id": structure.id,
        "date_start": date(2026, 1, 1),
        "state": "open",
    })
else:
    contract.write({"wage": WAGE, "struct_id": structure.id, "state": "open"})

payslip = env["hr.payslip"].create({
    "name": "Payroll smoke test",
    "employee_id": employee.id,
    "contract_id": contract.id,
    "struct_id": structure.id,
    "date_from": DATE_FROM,
    "date_to": DATE_TO,
})

try:
    payslip.compute_sheet()
except Exception as exc:
    # hr_payroll_community wraps every rule failure in a bare except and
    # reports only the rule name, with no traceback. Printing the raw message
    # is the most information available.
    print("\nCOMPUTE FAILED: %s" % exc)
    raise

print("\n%-26s %14s" % ("Rule", "Amount"))
print("-" * 41)
for line in payslip.line_ids.sorted("sequence"):
    print("%-26s %14.2f" % (line.name[:26], line.total))

net = payslip.line_ids.filtered(lambda l: l.code == "NET")
print("-" * 41)
print("%-26s %14.2f" % ("NET", net.total if net else 0.0))

expected = 70441.65
actual = net.total if net else 0.0
if abs(actual - expected) < 0.01:
    print("\nMatches the expected net of %.2f" % expected)
else:
    print("\nMISMATCH: expected %.2f, got %.2f — difference %.2f"
          % (expected, actual, actual - expected))

# Leave nothing behind: this runs against a test database, but a stray
# employee and payslip would still confuse the next person to look.
payslip.unlink()
print("\nTest payslip removed. The test employee and contract remain, so the")
print("test can be re-run without recreating them.")
