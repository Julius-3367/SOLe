# -*- coding: utf-8 -*-
"""
Seed Softlink Options Limited KPI data — July 2026 demo.

Usage:
  python3 /home/julius/odoo-19/odoo-bin \
    -c /home/julius/SOLe/sole.conf \
    -d sole_odoo shell \
    < /home/julius/SOLe/seed_softlink_kpi.py
"""

# env is injected by odoo-bin shell as SUPERUSER — no sudo() needed  # noqa: F821

print("\n" + "=" * 64)
print("  Softlink KPI Seed — July 2026")
print("=" * 64)

# ── 1. CATEGORIES ────────────────────────────────────────────────────
CAT_COLORS = {
    'Financial Sustainability':              3,   # yellow/gold
    'Customer Success & Growth':             4,   # light blue
    'Sales & Business Development':          1,   # red/orange
    'Marketing':                             6,   # pink
    'Project Delivery':                      7,   # teal
    'Infrastructure & Support':              8,   # dark blue
    'Tendering & Strategic Growth':          2,   # orange
    'People, Learning & Culture':            5,   # purple
    'Governance, Compliance & Risk':         9,   # dark red
    'Innovation & Continuous Improvement':  10,   # green
}

cats = {}
for name, color in CAT_COLORS.items():
    cat = env['sole.kpi.category'].search([('name', '=', name)], limit=1)
    if cat:
        cat.write({'color': color})
    else:
        cat = env['sole.kpi.category'].create({'name': name, 'color': color,
                                               'sequence': list(CAT_COLORS).index(name) * 10 + 10})
    cats[name] = cat

print(f"  [OK] {len(cats)} categories ready")

# ── 2. ROLES ─────────────────────────────────────────────────────────
ROLE_DEF = [
    ('CEO',                          'CEO'),
    ('Finance',                      'FIN'),
    ('Customer Success',             'CS'),
    ('Sales & Business Development', 'SBD'),
    ('Marketing',                    'MKT'),
    ('Project Delivery',             'PM'),
    ('Infrastructure & Support',     'INFRA'),
    ('People & Culture',             'HR'),
    ('Leadership',                   'LEAD'),
]

roles = {}
for rname, rcode in ROLE_DEF:
    role = env['sole.kpi.role'].search([('code', '=', rcode)], limit=1)
    if not role:
        role = env['sole.kpi.role'].create({'name': rname, 'code': rcode})
    roles[rcode] = role

print(f"  [OK] {len(roles)} roles ready")

# ── 3. DUMMY USERS ───────────────────────────────────────────────────
kpi_user_gid = env.ref('sole_kpi.group_kpi_user').id

STAFF = [
    # (display_name, login, role_code)
    ('Julius Korir',    'admin',                                  'CEO'),
    ('Mercy Wanjiku',   'mercy.w@softlinkoptions.co.ke',          'FIN'),
    ('David Kamau',     'david.k@softlinkoptions.co.ke',          'CS'),
    ('Brian Ochieng',   'brian.o@softlinkoptions.co.ke',          'SBD'),
    ('Aisha Mwangi',    'aisha.m@softlinkoptions.co.ke',          'MKT'),
    ('Peter Njoroge',   'peter.n@softlinkoptions.co.ke',          'PM'),
    ('Samuel Kariuki',  'samuel.k@softlinkoptions.co.ke',         'INFRA'),
    ('Grace Mutua',     'grace.mu@softlinkoptions.co.ke',         'HR'),
    ('Faith Otieno',    'faith.o@softlinkoptions.co.ke',          'LEAD'),
]

staff = {}
for fullname, login, rcode in STAFF:
    u = env['res.users'].search([('login', '=', login)], limit=1)
    if not u:
        u = env['res.users'].create({
            'name': fullname,
            'login': login,
            'email': login if '@' in login else login + '@softlinkoptions.co.ke',
            'password': 'Softlink@2026',
            'group_ids': [(4, kpi_user_gid)],
        })
    else:
        u.write({'group_ids': [(4, kpi_user_gid)]})
    staff[rcode] = u
    roles[rcode].write({'user_ids': [(4, u.id)]})

print(f"  [OK] {len(staff)} users ready")

# ── 4. KPI INDICATORS ────────────────────────────────────────────────
# (category, name, target, unit, direction, [role_codes], weight, target_display)
INDICATORS = [
    # ─ Financial Sustainability ──────────────────────────────────────
    ('Financial Sustainability', 'Revenue',
     1_000_000, 'currency',   'higher', ['CEO'],       1.5, 'KES 1,000,000'),
    ('Financial Sustainability', 'Cash Collection Rate',
     95,        'percentage', 'higher', ['FIN'],        1.2, '≥95%'),
    ('Financial Sustainability', 'Gross Profit Margin',
     40,        'percentage', 'higher', ['FIN'],        1.2, '≥40%'),
    ('Financial Sustainability', 'Managed Services MRR Growth',
     100_000,   'currency',   'higher', ['CEO'],        1.2, '+KES 100,000'),
    ('Financial Sustainability', 'Recurring Revenue Ratio',
     50,        'percentage', 'higher', ['CEO'],        1.0, '≥50%'),

    # ─ Customer Success & Growth ─────────────────────────────────────
    ('Customer Success & Growth', 'Customer Retention Rate',
     95,        'percentage', 'higher', ['CS'],         1.5, '≥95%'),
    ('Customer Success & Growth', 'Upsell Revenue',
     300_000,   'currency',   'higher', ['CS'],         1.2, 'KES 300,000'),
    ('Customer Success & Growth', 'Cross-sell Opportunities Identified',
     10,        'count',      'higher', ['CS'],         1.0, '10'),
    ('Customer Success & Growth', 'Customer Engagement Visits',
     84,        'count',      'higher', ['CS'],         1.0, '21/week'),
    ('Customer Success & Growth', 'Customer Satisfaction (CSAT)',
     90,        'percentage', 'higher', ['CS'],         1.5, '≥90%'),
    ('Customer Success & Growth', 'Customer Referrals Generated',
     2,         'count',      'higher', ['CS'],         1.0, '2'),

    # ─ Sales & Business Development ──────────────────────────────────
    ('Sales & Business Development', 'Qualified Leads Generated',
     40,        'count',      'higher', ['SBD'],        1.2, '40'),
    ('Sales & Business Development', 'Discovery Meetings Held',
     20,        'count',      'higher', ['SBD'],        1.0, '20'),
    ('Sales & Business Development', 'Proposals Submitted',
     12,        'count',      'higher', ['SBD'],        1.0, '12'),
    ('Sales & Business Development', 'New Contract Value Signed',
     1_500_000, 'currency',   'higher', ['SBD'],        1.5, 'KES 1,500,000'),
    ('Sales & Business Development', 'Strategic Partnerships Established',
     1,         'count',      'higher', ['SBD'],        1.0, '1 per Quarter'),

    # ─ Marketing ─────────────────────────────────────────────────────
    ('Marketing', 'Website Enquiries',
     20,        'count',      'higher', ['MKT'],        1.0, '20'),
    ('Marketing', 'Marketing Qualified Leads (MQLs)',
     20,        'count',      'higher', ['MKT'],        1.0, '20'),
    ('Marketing', 'LinkedIn Posts Published',
     12,        'count',      'higher', ['MKT'],        0.8, '12'),
    ('Marketing', 'Videos Produced',
     8,         'count',      'higher', ['MKT'],        0.8, '8'),
    ('Marketing', 'Website Articles Published',
     4,         'count',      'higher', ['MKT'],        0.8, '4'),
    ('Marketing', 'Customer Success Story Published',
     1,         'count',      'higher', ['MKT'],        1.0, '1'),
    ('Marketing', 'Company Newsletter Published',
     1,         'count',      'higher', ['MKT'],        0.8, '1'),
    ('Marketing', 'Webinar / Training Event Held',
     1,         'count',      'higher', ['MKT'],        1.0, '1'),

    # ─ Project Delivery ───────────────────────────────────────────────
    ('Project Delivery', 'Projects Delivered On Time',
     90,        'percentage', 'higher', ['PM'],         1.5, '≥90%'),
    ('Project Delivery', 'Project Gross Margin',
     35,        'percentage', 'higher', ['PM'],         1.2, '≥35%'),
    ('Project Delivery', 'UAT Sign-offs Completed',
     100,       'percentage', 'higher', ['PM'],         1.2, '100%'),
    ('Project Delivery', 'Project Acceptance Certificates Signed',
     100,       'percentage', 'higher', ['PM'],         1.2, '100%'),
    ('Project Delivery', 'Project Documentation Completed',
     100,       'percentage', 'higher', ['PM'],         1.0, '100%'),
    ('Project Delivery', 'Change Requests Managed Through Process',
     100,       'percentage', 'higher', ['PM'],         1.0, '100%'),

    # ─ Infrastructure & Support ───────────────────────────────────────
    ('Infrastructure & Support', 'Server Uptime',
     99.9,      'percentage', 'higher', ['INFRA'],      1.5, '≥99.9%'),
    ('Infrastructure & Support', 'SLA Compliance',
     95,        'percentage', 'higher', ['INFRA'],      1.2, '≥95%'),
    ('Infrastructure & Support', 'Backup Success Rate',
     100,       'percentage', 'higher', ['INFRA'],      1.2, '100%'),
    ('Infrastructure & Support', 'Critical Incidents',
     2,         'count',      'lower',  ['INFRA'],      1.5, '≤2'),
    ('Infrastructure & Support', 'Preventive Maintenance Completed',
     100,       'percentage', 'higher', ['INFRA'],      1.0, '100%'),
    ('Infrastructure & Support', 'Avg Ticket Resolution Within SLA',
     95,        'percentage', 'higher', ['INFRA'],      1.0, '≥95%'),

    # ─ Tendering & Strategic Growth ──────────────────────────────────
    ('Tendering & Strategic Growth', 'Tender Opportunities Identified',
     20,        'count',      'higher', ['SBD'],        1.0, '20'),
    ('Tendering & Strategic Growth', 'Tenders Submitted',
     5,         'count',      'higher', ['SBD'],        1.2, '4–6'),
    ('Tendering & Strategic Growth', 'Tender Success Rate',
     20,        'percentage', 'higher', ['SBD'],        1.5, '≥20% (Annual)'),
    ('Tendering & Strategic Growth', 'Proposal Library Updated',
     100,       'percentage', 'higher', ['SBD'],        0.8, '100%'),
    ('Tendering & Strategic Growth', 'Strategic Bid / Partner Meetings',
     4,         'count',      'higher', ['SBD'],        1.0, '4'),

    # ─ People, Learning & Culture ─────────────────────────────────────
    ('People, Learning & Culture', 'Internal Training Sessions',
     2,         'count',      'higher', ['HR'],         1.2, '2'),
    ('People, Learning & Culture', 'Lunch & Learn Sessions',
     1,         'count',      'higher', ['HR'],         1.0, '1'),
    ('People, Learning & Culture', 'Avg Training Hours per Employee',
     4,         'hours',      'higher', ['HR'],         1.0, '4 Hours'),
    ('People, Learning & Culture', 'Professional Certifications Progress',
     100,       'percentage', 'higher', ['HR'],         1.0, 'As Per Plan'),
    ('People, Learning & Culture', 'Performance Reviews Completed',
     100,       'percentage', 'higher', ['HR'],         1.5, '100%'),
    ('People, Learning & Culture', 'Employee Retention',
     95,        'percentage', 'higher', ['HR'],         1.5, '≥95%'),

    # ─ Governance, Compliance & Risk ─────────────────────────────────
    ('Governance, Compliance & Risk', 'Policies Reviewed / Developed',
     2,         'count',      'higher', ['LEAD'],       1.0, '2'),
    ('Governance, Compliance & Risk', 'Internal Compliance Audit Completed',
     1,         'count',      'higher', ['LEAD'],       1.5, '1'),
    ('Governance, Compliance & Risk', 'Compliance Action Items Closed',
     90,        'percentage', 'higher', ['LEAD'],       1.2, '≥90%'),
    ('Governance, Compliance & Risk', 'Monthly KPI Review Meeting Held',
     100,       'percentage', 'higher', ['LEAD'],       1.2, '100%'),
    ('Governance, Compliance & Risk', 'Board Reports Submitted On Time',
     100,       'percentage', 'higher', ['LEAD'],       1.5, '100%'),

    # ─ Innovation & Continuous Improvement ───────────────────────────
    ('Innovation & Continuous Improvement', 'New Service Improvements Introduced',
     1,         'count',      'higher', ['LEAD'],       1.0, '1'),
    ('Innovation & Continuous Improvement', 'Internal Process Improvements Implemented',
     2,         'count',      'higher', ['LEAD'],       1.0, '2'),
    ('Innovation & Continuous Improvement', 'Automation Initiatives Completed',
     1,         'count',      'higher', ['LEAD'],       1.2, '1'),
    ('Innovation & Continuous Improvement', 'Customer Improvement Suggestions Implemented',
     2,         'count',      'higher', ['CS'],         1.0, '2'),
]

inds = {}
for seq, (cat_name, name, target, unit, direction, rcodes, weight, tdisplay) in enumerate(INDICATORS, 1):
    ind = env['sole.kpi.indicator'].search([('name', '=', name)], limit=1)
    role_cmds = [(4, roles[rc].id) for rc in rcodes]
    vals = {
        'category_id': cats[cat_name].id,
        'target': target,
        'unit': unit,
        'direction': direction,
        'role_ids': role_cmds,
        'weight': weight,
        'target_display': tdisplay,
        'sequence': seq * 10,
        'active': True,
    }
    if not ind:
        vals['name'] = name
        ind = env['sole.kpi.indicator'].create(vals)
    else:
        ind.write(vals)
    inds[name] = ind

print(f"  [OK] {len(inds)} KPI indicators ready")

# ── 5. PERIOD ────────────────────────────────────────────────────────
period = env['sole.kpi.period'].search([('name', '=', 'July 2026')], limit=1)
if not period:
    period = env['sole.kpi.period'].create({
        'name': 'July 2026',
        'date_start': '2026-07-01',
        'date_end': '2026-07-31',
        'state': 'draft',
    })
    print("  [OK] Period 'July 2026' created")
else:
    print("  [OK] Period 'July 2026' found")

# ── 6. KPI ENTRIES ───────────────────────────────────────────────────
# (indicator_name, role_code, actual, notes, trend)
# Target achievement mix: ~60% Green, 25% Amber, 15% Red — realistic first month
ENTRIES = [
    # Financial Sustainability
    ('Revenue',                             'CEO',   850_000,
     'Strong pipeline; 3 contracts delayed to August.', 'up'),
    ('Cash Collection Rate',                'FIN',   92.0,
     'Outstanding invoices from 2 key clients being followed up.', 'stable'),
    ('Gross Profit Margin',                 'FIN',   38.5,
     'Slightly below due to infrastructure cost increase.', 'down'),
    ('Managed Services MRR Growth',         'CEO',   75_000,
     '3 new managed-services clients onboarded; 2 pending activation.', 'up'),
    ('Recurring Revenue Ratio',             'CEO',   48.0,
     '2 project clients converting to managed services next month.', 'stable'),

    # Customer Success & Growth
    ('Customer Retention Rate',             'CS',    97.5,
     'Lost 1 client due to budget cuts; all others renewed.', 'up'),
    ('Upsell Revenue',                      'CS',    195_000,
     'Only 2 upsell deals closed; 4 more in negotiation.', 'down'),
    ('Cross-sell Opportunities Identified', 'CS',    13,
     'Exceeded target — strong pipeline identified.', 'up'),
    ('Customer Engagement Visits',          'CS',    72,
     'Missed 12 visits due to 2 staff on planned leave.', 'stable'),
    ('Customer Satisfaction (CSAT)',        'CS',    93.5,
     'Positive feedback from Q2 NPS survey.', 'up'),
    ('Customer Referrals Generated',        'CS',    3,
     '1 referral converted to a signed contract.', 'up'),

    # Sales & Business Development
    ('Qualified Leads Generated',           'SBD',   35,
     'Digital campaigns performing well; slightly below target.', 'stable'),
    ('Discovery Meetings Held',             'SBD',   19,
     'One meeting rescheduled to 1 August.', 'stable'),
    ('Proposals Submitted',                 'SBD',   10,
     '2 proposals delayed due to client spec changes.', 'down'),
    ('New Contract Value Signed',           'SBD',   1_100_000,
     'Solid month; 3 large deals expected in August.', 'up'),
    ('Strategic Partnerships Established',  'SBD',   0,
     'Partnership with ICT Authority in advanced negotiation.', 'stable'),

    # Marketing
    ('Website Enquiries',                   'MKT',   26,
     'SEO improvements driving 30% more organic traffic.', 'up'),
    ('Marketing Qualified Leads (MQLs)',    'MKT',   19,
     '1 below target; quality improving vs volume.', 'stable'),
    ('LinkedIn Posts Published',            'MKT',   14,
     '2 posts reached 5,000+ impressions.', 'up'),
    ('Videos Produced',                     'MKT',   6,
     '2 videos deferred due to studio availability.', 'down'),
    ('Website Articles Published',          'MKT',   4,
     'On target.', 'stable'),
    ('Customer Success Story Published',    'MKT',   1,
     'Baraka Savings & Credit case study published.', 'stable'),
    ('Company Newsletter Published',        'MKT',   1,
     'July issue sent to 847 subscribers.', 'stable'),
    ('Webinar / Training Event Held',       'MKT',   1,
     'Cybersecurity awareness webinar — 112 attendees.', 'up'),

    # Project Delivery
    ('Projects Delivered On Time',          'PM',    87.0,
     '1 of 8 projects delayed 5 days — client scope change.', 'stable'),
    ('Project Gross Margin',                'PM',    37.5,
     'Strong margins on Nakuru County contract.', 'up'),
    ('UAT Sign-offs Completed',             'PM',    100,
     'All active UATs completed within sprint.', 'stable'),
    ('Project Acceptance Certificates Signed', 'PM', 100,
     'All Q2 project closures documented.', 'stable'),
    ('Project Documentation Completed',     'PM',    95.0,
     '1 project doc pending final client sign-off.', 'down'),
    ('Change Requests Managed Through Process','PM',  100,
     'All CRs formally logged and approved.', 'stable'),

    # Infrastructure & Support
    ('Server Uptime',                       'INFRA', 99.97,
     '18-minute unplanned downtime on 14 July (resolved in 22 min).', 'stable'),
    ('SLA Compliance',                      'INFRA', 93.0,
     '3 P2 tickets exceeded 4-hour SLA target.', 'down'),
    ('Backup Success Rate',                 'INFRA', 100,
     'All backup jobs ran successfully.', 'stable'),
    ('Critical Incidents',                  'INFRA', 1,
     '1 critical incident (network outage) resolved in 2 hrs.', 'up'),
    ('Preventive Maintenance Completed',    'INFRA', 100,
     'All scheduled PM tasks completed on time.', 'stable'),
    ('Avg Ticket Resolution Within SLA',    'INFRA', 91.0,
     'Improving trend; 2 engineers completed ITIL training.', 'up'),

    # Tendering & Strategic Growth
    ('Tender Opportunities Identified',     'SBD',   23,
     'Strong pipeline from government portal monitoring.', 'up'),
    ('Tenders Submitted',                   'SBD',   5,
     'Within target range (4–6).', 'stable'),
    ('Tender Success Rate',                 'SBD',   15.0,
     '2 of 13 tenders won YTD; 2 results still pending.', 'down'),
    ('Proposal Library Updated',            'SBD',   100,
     'All templates updated with new pricing structures.', 'stable'),
    ('Strategic Bid / Partner Meetings',    'SBD',   5,
     'Additional meeting with Microsoft partner team.', 'up'),

    # People, Learning & Culture
    ('Internal Training Sessions',          'HR',    2,
     'Cloud Architecture and Client Communication training held.', 'stable'),
    ('Lunch & Learn Sessions',              'HR',    1,
     'AI tools for productivity — 22 staff attended.', 'stable'),
    ('Avg Training Hours per Employee',     'HR',    3.5,
     'Slightly below 4-hr target; 2 sessions ran short.', 'stable'),
    ('Professional Certifications Progress','HR',    80.0,
     '4 of 5 targeted certifications on track per plan.', 'down'),
    ('Performance Reviews Completed',       'HR',    100,
     'All Q2 appraisals completed and signed off.', 'stable'),
    ('Employee Retention',                  'HR',    97.4,
     '1 resignation replaced internally; strong retention.', 'up'),

    # Governance, Compliance & Risk
    ('Policies Reviewed / Developed',       'LEAD',  3,
     'Data Protection and Remote Work policies updated.', 'up'),
    ('Internal Compliance Audit Completed', 'LEAD',  1,
     'July audit completed; 6 minor findings documented.', 'stable'),
    ('Compliance Action Items Closed',      'LEAD',  88.0,
     '14 of 16 items closed; 2 items require vendor input.', 'stable'),
    ('Monthly KPI Review Meeting Held',     'LEAD',  100,
     'Leadership review held 25 July.', 'stable'),
    ('Board Reports Submitted On Time',     'LEAD',  100,
     'Board pack submitted 3 days ahead of schedule.', 'up'),

    # Innovation & Continuous Improvement
    ('New Service Improvements Introduced', 'LEAD',  1,
     'Automated client onboarding portal launched.', 'up'),
    ('Internal Process Improvements Implemented', 'LEAD', 2,
     'Invoice automation and ticketing workflow improved.', 'up'),
    ('Automation Initiatives Completed',    'LEAD',  0,
     'Payroll automation deferred to August — HR input pending.', 'down'),
    ('Customer Improvement Suggestions Implemented', 'CS', 2,
     'Client portal enhancements and SLA notification emails live.', 'up'),
]

Entry = env['sole.kpi.entry'].with_user(1)
created = updated = 0

for ind_name, rcode, actual, notes, trend in ENTRIES:
    ind = inds.get(ind_name)
    if not ind:
        print(f"  [WARN] Indicator not found: {ind_name}")
        continue
    user = staff.get(rcode)
    role = roles.get(rcode)
    if not user or not role:
        print(f"  [WARN] User/role not found for code: {rcode}")
        continue

    existing = Entry.search([
        ('period_id', '=', period.id),
        ('indicator_id', '=', ind.id),
        ('user_id', '=', user.id),
    ], limit=1)

    vals = {'actual': actual, 'notes': notes, 'trend': trend, 'role_id': role.id}
    if existing:
        existing.write(vals)
        updated += 1
    else:
        Entry.create({**vals,
                      'period_id': period.id,
                      'indicator_id': ind.id,
                      'user_id': user.id})
        created += 1

print(f"  [OK] Entries: {created} created, {updated} updated")

# ── COMMIT ───────────────────────────────────────────────────────────
env.cr.commit()

print("\n" + "=" * 64)
print("  DONE — July 2026 scorecard seeded successfully")
print(f"  Period ID : {period.id}")
print(f"  Indicators: {len(inds)}")
print(f"  Entries   : {created + updated}")
print("=" * 64 + "\n")
