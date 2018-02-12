# -*- coding: utf-8 -*-
{
    'name': "Budget lines reporting",
    'summary': "Add a reporting menu for budget lines",
    'author': "Praxya, "
              "Odoo Community Association (OCA)",
    'contributors': ['Rubén Cabrera Martínez <rcabrera@praxya.com>'],
    'website': 'https://github.com/OCA/account-budgeting',
    'category': 'Accounting',
    'version': '8.0.0.1',
    'license': 'AGPL-3',
    'depends': [
        'account_budget',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/budget_lines_report.xml',
    ],
    "installable": True,
}
