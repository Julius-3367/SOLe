# Put expenses on the right accounts.
#
# Run inside the Odoo shell on Zebra:
#   docker exec -i sole_app odoo shell -d sole_odoo --no-http < tools/fix_expense_accounts.py
#
# ── The problem ──────────────────────────────────────────────────────────────
#
# The expense products in this database have no expense account configured, so
# Odoo falls back to the product category default — 500100 — for every one of
# them. This was invisible until expenses were created here: the 2024 and 2025
# records look correct only because their account_id came across in the
# migration, not because the products were ever set up.
#
# It surfaced when 113 imported records all landed on 500100 instead of
# spreading across the 25 accounts the old system used. It affects every new
# expense anyone enters, not only the imported ones.
#
# ── What this does ───────────────────────────────────────────────────────────
#
# 1. Sets each expense product's expense account from the account that
#    product's own historical expenses actually used in this database. That is
#    the treatment the accounts already reflect, so it changes no history — it
#    makes future expenses land where past ones did.
#
# 2. Corrects the account on the imported draft records, taking each one from
#    the account the old system posted that exact record to.
#
# DRY_RUN = True reports and writes nothing.

import psycopg2
import psycopg2.extras

from odoo.tools import config as odoo_config

DRY_RUN = True
CUTOFF = "2026-06-30"
SOURCE_DB = "odoo17_temp"
TAG = "[migrated from old ERP]"


def source_dsn():
    parts = ["dbname=%s" % SOURCE_DB]
    for key, param in (
        ("db_user", "user"),
        ("db_password", "password"),
        ("db_host", "host"),
        ("db_port", "port"),
    ):
        value = odoo_config.get(key)
        if value:
            parts.append("%s=%s" % (param, value))
    return " ".join(parts)


Expense = env["hr.expense"]
Product = env["product.product"]
Account = env["account.account"]
company = env.company

# Account code -> account record, for this company.
code_to_account = {}
for acc in Account.search([]):
    code = acc.code
    if code:
        code_to_account[code] = acc


# ── 1. Configure the products ────────────────────────────────────────────────
# Work out each product's account from expenses that predate the import, so
# the imported records — which are currently wrong — do not skew the answer.
env.cr.execute(
    """
    SELECT e.product_id, a.code_store->>%s AS code, count(*) AS n
    FROM hr_expense e
    JOIN account_account a ON a.id = e.account_id
    WHERE e.product_id IS NOT NULL
      AND e.name NOT LIKE %s
    GROUP BY 1, 2
    """,
    (str(company.id), "%" + TAG + "%"),
)
best = {}
for r in env.cr.dictfetchall():
    prev = best.get(r["product_id"])
    if prev is None or r["n"] > prev[1]:
        best[r["product_id"]] = (r["code"], r["n"])

print("Products with historical expenses: %d\n" % len(best))
print("Product account configuration:")
changed = 0
for pid, (code, n) in sorted(best.items()):
    product = Product.browse(pid)
    account = code_to_account.get(code)
    if not account:
        print("   %-32s -> account %s not found, skipped" % (product.name[:32], code))
        continue
    current = product.product_tmpl_id.property_account_expense_id
    if current and current.id == account.id:
        continue
    print("   %-32s %s -> %s   (%d past expenses)"
          % (product.name[:32], current.code if current else "(none)", code, n))
    changed += 1
    if not DRY_RUN:
        product.product_tmpl_id.property_account_expense_id = account.id

print("\nProducts needing a change: %d" % changed)


# ── 2. Correct the imported drafts ───────────────────────────────────────────
src = psycopg2.connect(source_dsn())
cur = src.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute(
    """
    SELECT e.name, e.date, e.total_amount, a.code AS account_code
    FROM hr_expense e
    LEFT JOIN account_account a ON a.id = e.account_id
    WHERE e.date > %s
    """,
    (CUTOFF,),
)
old_rows = cur.fetchall()
src.close()

# Key each source record by what the import wrote into the new system.
old_by_key = {}
for r in old_rows:
    key = (str(r["date"]), round(float(r["total_amount"] or 0), 2),
           (r["name"] or "").strip())
    old_by_key.setdefault(key, []).append(r["account_code"])

imported = Expense.search([("name", "like", TAG)])
print("\nImported records found: %d" % len(imported))

fixed = 0
unmatched = []
for exp in imported:
    base_name = exp.name.replace(TAG, "").strip()
    key = (str(exp.date), round(float(exp.total_amount or 0), 2), base_name)
    codes = old_by_key.get(key)
    if not codes:
        unmatched.append((exp.id, exp.date, base_name, exp.total_amount))
        continue
    account = code_to_account.get(codes[0])
    if not account:
        unmatched.append((exp.id, exp.date, base_name, exp.total_amount))
        continue
    if exp.account_id.id == account.id:
        continue
    fixed += 1
    if not DRY_RUN:
        exp.account_id = account.id

print("Records whose account would change: %d" % fixed)
if unmatched:
    print("\nCould not match back to a source record:")
    for eid, dt, nm, amt in unmatched:
        print("   %-7s %s %-30s %10.2f" % (eid, dt, nm[:30], float(amt or 0)))

if DRY_RUN:
    print("\nDRY RUN — nothing written. Set DRY_RUN = False to apply.")
else:
    env.cr.commit()
    print("\nApplied. Re-run the account comparison to confirm the two systems")
    print("agree account by account.")
