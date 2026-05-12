# -*- coding: utf-8 -*-

# Odoo Proprietary License v1.0
#
# This software and associated files (the “Software”) may only be
# used (executed, modified, executed after modifications) if you have
# purchased a valid license from the authors, typically via Odoo Apps,
# or if you have received a written agreement from the authors of the
# Software (see the COPYRIGHT file).
#
# You may develop Odoo modules that use the Software as a library
# (typically by depending on it, importing it and using its resources),
# but without copying any source code or material from the Software.
# You may distribute those modules under the license of your choice,
# provided that this license is compatible with the terms of the Odoo
# Proprietary License (For example: LGPL, MIT, or proprietary licenses
# similar to this one).
#
# It is forbidden to publish, distribute, sublicense, or sell copies of
# the Software or modified copies of the Software.
#
# The above copyright notice and this permission notice must be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
# USE OR OTHER DEALINGS IN THE SOFTWARE.

{
    'name': 'Customer Invoice Statements Reports',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'license': 'OPL-1',
    'summary': """
        Partner Invoice/ Bills Statement Reports
    """,
    'depends': [
        'base',
        'account',
    ],
    'author': 'SugarClone ERP',
    'support': 'sugarcloneerp@gmail.com',
    'price': 12,
    'currency': 'USD',
    'description': """ Updates Below
    - Partner Invoice/ Bills Statements
    """,
    'data': [
        'security/ir.model.access.csv',
        'report/paperformat.xml',
        'report/inv_statement_template.xml',
        'report/report_tag.xml',
        'wizard/inv_statement_wiz.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/inv_statements_sce/static/src/scss/inv_statement.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
