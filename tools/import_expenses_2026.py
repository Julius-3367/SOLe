# Import the 2026 expenses that exist in the old ERP but not in the new one.
#
# Background: 2024 and 2025 reconcile exactly between the two systems. Only
# 2026 differs, by 114 records, all dated after the migration cutover — entries
# staff made in the old ERP while both systems were in use.
#
# Run inside the Odoo shell on Zebra:
#   docker exec -i sole_app odoo shell -d sole_odoo --no-http < tools/import_expenses_2026.py
#
# DRY_RUN = True reports what it would do and writes nothing. Read the report,
# then set DRY_RUN = False and run it again.
#
# Records are created as DRAFT. They are not submitted, approved or posted, so
# nothing reaches the ledger until an accountant approves them in the UI.
#
# ── How products are matched ─────────────────────────────────────────────────
#
# Matching on product NAME alone is not safe here. Several names exist more
# than once in the new database — "Meals" appears three times — and the copies
# post to different expense accounts. An earlier version of this script chose
# by popularity and picked the wrong one: old "Meals" posts to 512200, but the
# most-used new "Meals" posts to 510100.
#
# So each record is matched on the ACCOUNT the old system actually posted it
# to. Among products sharing a name, the one whose own expenses land on that
# same account wins. This also decides which account a newly created product
# should use, and rescues records that have no product at all, by finding the
# product that posts where the old record posted.

import psycopg2
import psycopg2.extras

from odoo.tools import config as odoo_config

DRY_RUN = True
CREATE_MISSING_PRODUCTS = False
CUTOFF = "2026-06-30"
SOURCE_DB = "odoo17_temp"

# Marker written into every imported record so the whole batch can be found
# again — or reversed — without guessing.
TAG = "[migrated from old ERP]"


class WouldCreate:
    """Stand-in during a dry run for a product a real run would create.

    Without this, only the first record of a missing product counts as ready
    and the rest are reported as skipped, because the decision cache stores a
    failure. The dry run would then under-report what a real run does.
    """

    id = None


def source_dsn():
    """Connection string for the old database.

    Built from Odoo's own configuration rather than hard-coded, so the
    credentials stay in odoo.conf and never reach this repository — which is
    public.
    """
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


# ── Read the source records ──────────────────────────────────────────────────
src = psycopg2.connect(source_dsn())
cur = src.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute(
    """
    SELECT e.id            AS old_id,
           e.name          AS name,
           e.date          AS date,
           e.total_amount  AS total_amount,
           e.quantity      AS quantity,
           e.payment_mode  AS payment_mode,
           emp.name        AS employee_name,
           t.name->>'en_US' AS product_name,
           a.code          AS account_code
    FROM hr_expense e
    LEFT JOIN hr_employee emp     ON emp.id = e.employee_id
    LEFT JOIN product_product p   ON p.id = e.product_id
    LEFT JOIN product_template t  ON t.id = p.product_tmpl_id
    LEFT JOIN account_account a   ON a.id = e.account_id
    WHERE e.date > %s
    ORDER BY e.date, e.id
    """,
    (CUTOFF,),
)
rows = cur.fetchall()
src.close()

print("Source records to import: %d" % len(rows))

Expense = env["hr.expense"]
Employee = env["hr.employee"]
Product = env["product.product"]
Account = env["account.account"]
company = env.company

# ── Which account does each existing product post to in THIS database? ───────
env.cr.execute(
    """
    SELECT e.product_id, a.code_store->>%s AS code, count(*) AS n
    FROM hr_expense e
    JOIN account_account a ON a.id = e.account_id
    WHERE e.product_id IS NOT NULL
    GROUP BY 1, 2
    """,
    (str(company.id),),
)
product_account = {}
for r in env.cr.dictfetchall():
    prev = product_account.get(r["product_id"])
    if prev is None or r["n"] > prev[1]:
        product_account[r["product_id"]] = (r["code"], r["n"])
product_account = {pid: code for pid, (code, _n) in product_account.items()}

# Reverse lookup: account code -> products that post there
account_products = {}
for pid, code in product_account.items():
    account_products.setdefault(code, []).append(pid)


def resolve_product(name, account_code):
    """Return (product, explanation) for one source record."""
    if name:
        candidates = Product.search([("name", "=", name), ("can_be_expensed", "=", True)])
        if not candidates:
            candidates = Product.search([("name", "=", name)])
        if len(candidates) == 1:
            return candidates, "single match"
        if len(candidates) > 1:
            by_account = [p for p in candidates if product_account.get(p.id) == account_code]
            if len(by_account) == 1:
                return by_account[0], "account %s among %s" % (
                    account_code, candidates.ids)
            if len(by_account) > 1:
                return by_account[0], "account %s, %d products share it, took id %d" % (
                    account_code, len(by_account), by_account[0].id)
            return None, "name matched %s but none post to account %s" % (
                candidates.ids, account_code)
        # No product of that name exists at all.
        return None, "no product named %r" % name

    # Source record has no product. Fall back to the account it posted to.
    pids = account_products.get(account_code, [])
    if len(pids) == 1:
        return Product.browse(pids[0]), "no product on source; only product posting to %s" % account_code
    if len(pids) > 1:
        return None, "no product on source; %d products post to %s: %s" % (
            len(pids), account_code, pids)
    return None, "no product on source and nothing posts to account %s" % account_code


# ── Resolve employees by name ────────────────────────────────────────────────
employee_map = {}
for nm in sorted({r["employee_name"] for r in rows if r["employee_name"]}):
    found = Employee.search([("name", "=", nm)])
    if len(found) == 1:
        employee_map[nm] = found
    else:
        print("EMPLOYEE %-20s -> %d matches (unresolved)" % (nm, len(found)))

# ── Build the values ─────────────────────────────────────────────────────────
to_create = []
skipped = []
decisions = {}
created_products = {}

for r in rows:
    emp = employee_map.get(r["employee_name"])
    if not emp:
        skipped.append((r["old_id"], r["name"], r["total_amount"],
                        "no employee match: %s" % r["employee_name"]))
        continue

    key = (r["product_name"], r["account_code"])
    if key not in decisions:
        prod, why = resolve_product(r["product_name"], r["account_code"])
        if prod is None and CREATE_MISSING_PRODUCTS and r["product_name"]:
            account = Account.search([("code", "=", r["account_code"])], limit=1)
            if account:
                created_products[r["product_name"]] = r["account_code"]
                if DRY_RUN:
                    prod = WouldCreate()
                    why = "would create product, expense account %s" % r["account_code"]
                else:
                    prod = Product.create({
                        "name": r["product_name"],
                        "can_be_expensed": True,
                        "type": "service",
                        "property_account_expense_id": account.id,
                    })
                    why = "created product %d, expense account %s" % (
                        prod.id, r["account_code"])
            else:
                why += "; account %s not found either" % r["account_code"]
        decisions[key] = (prod, why)
    prod, why = decisions[key]

    if prod is None:
        skipped.append((r["old_id"], r["name"], r["total_amount"], why))
        continue

    to_create.append({
        "name": "%s %s" % (r["name"] or r["product_name"], TAG),
        "employee_id": emp.id,
        "product_id": prod.id,
        "date": r["date"],
        "quantity": float(r["quantity"] or 1.0) or 1.0,
        "total_amount_currency": float(r["total_amount"] or 0.0),
        "payment_mode": r["payment_mode"] or "own_account",
        "company_id": company.id,
        "currency_id": company.currency_id.id,
    })

# ── Report ───────────────────────────────────────────────────────────────────
print("\nProduct decisions:")
for (name, code), (prod, why) in sorted(decisions.items(), key=lambda x: str(x[0])):
    print("   %-30s acct %-8s -> %-8s  %s"
          % (name or "(none)", code or "(none)",
             ("SKIP" if prod is None else (prod.id or "NEW")), why))

if created_products:
    print("\nProducts that would be created:")
    for nm, code in sorted(created_products.items()):
        print("   %-30s expense account %s" % (nm, code))

print("\nReady to create : %d" % len(to_create))
print("Skipped         : %d" % len(skipped))
print("Value ready     : %.2f" % sum(v["total_amount_currency"] for v in to_create))
print("Value skipped   : %.2f" % sum(float(s[2] or 0) for s in skipped))

if skipped:
    print("\nSkipped records:")
    for old_id, nm, amt, reason in skipped:
        print("   %-6s %-24s %10.2f  %s" % (old_id, (nm or "")[:24], float(amt or 0), reason))

if DRY_RUN:
    print("\nDRY RUN — nothing written. First five records that would be created:")
    for v in to_create[:5]:
        print("   %s  %-45s  %10.2f"
              % (v["date"], v["name"][:45], v["total_amount_currency"]))
    print("\nSet DRY_RUN = False to apply.")
else:
    created = Expense.create(to_create)
    env.cr.commit()
    print("\nCreated %d draft expenses (ids %d-%d)."
          % (len(created), min(created.ids), max(created.ids)))
    print("They are in Draft. Review and approve them in Expenses, and the")
    print("journal entries will be generated by Odoo on approval.")
    print("\nTo reverse this batch before approval:")
    print("   env['hr.expense'].search([('name','like','%s')]).unlink()" % TAG)
