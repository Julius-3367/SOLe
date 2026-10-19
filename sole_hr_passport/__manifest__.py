# -*- coding: utf-8 -*-
{
    "name": "Employee Passport Copy",
    "summary": "Upload a scan of the employee's passport next to the passport number",
    "description": """
Odoo keeps the passport number and expiry date on the employee but has nowhere
to store the passport itself, unlike the ID card, driving licence and work
permit. This adds a Passport Copy upload on the Personal tab, visible to HR
officers only.
""",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Employees",
    "author": "Softlink Options Limited",
    "website": "https://softlinkoptions.co.ke",
    "license": "LGPL-3",
    "depends": ["hr"],
    "data": [
        "views/hr_employee_views.xml",
    ],
    "installable": True,
}
