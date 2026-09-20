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
# check the product mapping, then set DRY_RUN = False and run it again.
#
# Records are created as DRAFT. They are not submitted, approved or posted, so
# nothing reaches the ledger until an accountant approves them in the UI.

import psycopg2
import psycopg2.extras

DRY_RUN = True
CREATE_MISSING_PRODUCTS = False
CUTOFF = "2026-06-30"
SRC_DSN = "dbname=odoo17_temp user=odoo19 host=sole_db"

# Marker written into every imported record so the whole batch can be found
# again — or reversed — without guessing.
TAG = "[migrated from old ERP]"

src = psycopg2.connect(SRC_DSN)
cur = src.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute(
    """
    SELECT e.id            AS old_id,
           e.name          AS name,
           e.date          AS date,
           e.total_amount  AS total_amount,
           e.quantity      AS quantity,
           e.state         AS old_state,
           e.payment_mode  AS payment_mode,
           emp.name        AS employee_name,
           t.name->>'en_US' AS product_name
    FROM hr_expense e
    LEFT JOIN hr_employee emp     ON emp.id = e.employee_id
    LEFT JOIN product_product p   ON p.id = e.product_id
    LEFT JOIN product_template t  ON t.id = p.product_tmpl_id
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
company = env.company

# ── Resolve employees by name ────────────────────────────────────────────────
employee_map = {}
for nm in sorted({r["employee_name"] for r in rows if r["employee_name"]}):
    found = Employee.search([("name", "=", nm)])
    if len(found) == 1:
        employee_map[nm] = found
    else:
        print("EMPLOYEE %-20s -> %d matches (unresolved)" % (nm, len(found)))

# ── Resolve products by name ─────────────────────────────────────────────────
# Several names match more than one product: ids 1 and 2 are Odoo's built-in
# defaults, the rest came across in the migration. Where there is a choice,
# prefer the product already used by existing expenses in this database, so
# imported records land on the same account as their 2024/2025 equivalents.
product_map = {}
missing_products = []
for nm in sorted({r["product_name"] for r in rows if r["product_name"]}):
    found = Product.search([("name", "=", nm), ("can_be_expensed", "=", True)])
    if not found:
        found = Product.search([("name", "=", nm)])
    if not found:
        missing_products.append(nm)
        continue
    if len(found) == 1:
        chosen = found
    else:
        usage = {
            p.id: Expense.search_count([("product_id", "=", p.id)]) for p in found
        }
        best = max(usage, key=usage.get)
        chosen = Product.browse(best)
        print(
            "PRODUCT  %-30s -> %d candidates %s, chose id %d (used by %d existing expenses)"
            % (nm, len(found), list(usage.keys()), chosen.id, usage[best])
        )
    product_map[nm] = chosen

if missing_products:
    print("\nProducts NOT present in this database:")
    for nm in missing_products:
        print("   %s" % nm)
    if not CREATE_MISSING_PRODUCTS:
        print("   (set CREATE_MISSING_PRODUCTS = True to create them)")

# ── Build the values ─────────────────────────────────────────────────────────
to_create = []
skipped = []
for r in rows:
    emp = employee_map.get(r["employee_name"])
    if not emp:
        skipped.append((r["old_id"], "no employee match: %s" % r["employee_name"]))
        continue

    prod = product_map.get(r["product_name"])
    if not prod and CREATE_MISSING_PRODUCTS and r["product_name"]:
        prod = Product.create({
            "name": r["product_name"],
            "can_be_expensed": True,
            "type": "service",
        })
        product_map[r["product_name"]] = prod
    if not prod:
        if r["product_name"] is None:
            skipped.append((r["old_id"], "no product recorded on the source record"))
        else:
            skipped.append((r["old_id"], "product not in database: %s" % r["product_name"]))
        continue

    qty = float(r["quantity"] or 1.0) or 1.0
    total = float(r["total_amount"] or 0.0)

    to_create.append({
        "name": "%s %s" % (r["name"] or r["product_name"], TAG),
        "employee_id": emp.id,
        "product_id": prod.id,
        "date": r["date"],
        "quantity": qty,
        "total_amount_currency": total,
        "payment_mode": r["payment_mode"] or "own_account",
        "company_id": company.id,
        "currency_id": company.currency_id.id,
    })

print("\nReady to create : %d" % len(to_create))
print("Skipped         : %d" % len(skipped))
print("Value           : %.2f" % sum(v["total_amount_currency"] for v in to_create))

if skipped:
    print("\nSkipped records (old ERP id, reason):")
    for old_id, reason in skipped:
        print("   %-8s %s" % (old_id, reason))

if DRY_RUN:
    print("\nDRY RUN — nothing written. First five records that would be created:")
    for v in to_create[:5]:
        print("   %s  %-45s  %10.2f" % (v["date"], v["name"][:45], v["total_amount_currency"]))
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
