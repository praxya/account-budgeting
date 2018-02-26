# -*- coding: utf-8 -*-
from openerp.tools import drop_view_if_exists, ustr
from openerp.osv import fields, osv


class BudgetLinesReport(osv.osv):
    _name = 'budget.lines.report'
    _description = "Budget lines"
    _auto = False
    # TODO: get a better name for reference
    _rec_name = 'date_to'

    # The next methods are copied from the original crossovered budget lines
    # model, but will need refactoring to get rid of the odoo ORM, which is
    # the origin of the problem

    def _perc(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.theoritical_amount != 0.00:
                res[line.id] = float(
                    (line.practical_amount or 0.0) / line.theoritical_amount)\
                    * 100
            else:
                res[line.id] = 0.00
        return res

    _columns = {
        'crossovered_budget_id': fields.many2one(
            'crossovered.budget',
            'Budget',
            readonly=True,
        ),
        'analytic_account_id': fields.many2one(
            'account.analytic.account',
            'Analytic Account',
            readonly=True,
        ),
        'general_budget_id': fields.many2one(
            'account.budget.post',
            'Budgetary Position',
            readonly=True,
        ),
        'date_from': fields.date('Start Date', readonly=True),
        'date_to': fields.date('End Date', readonly=True),
        'planned_amount': fields.float('Planned Amount', readonly=True,),
        'theoritical_amount': fields.float('Theoretical Amount', readonly=True),
        'practical_amount': fields.float(
            'Practical Amount',
            readonly=True
        ),
        # TODO: finish this fields
        # TODO: paid_date is a field in the budget line but is not used yet
        # 'paid_date': fields.date('Paid Date', readonly=True),
        'percentage': fields.function(
            _perc,
            string='Percentage',
            type='float',
        ),
    }
    _order = 'crossovered_budget_id desc'


    def _select(self):
        """
        Helper method: Sql select to get all the data for this report.
        """
        select_str = """
                SELECT min(l.id) as id,
                       l.crossovered_budget_id as crossovered_budget_id,
                       l.date_to as date_to,
                       l.date_from as date_form,
                       l.analytic_account_id as analytic_account_id,
                       /* Compute the theoretical amount for the elapsed time */
                       sum((
                        SELECT
                            CASE WHEN (l.paid_date IS NOT NULL
                                        AND l.paid_date >= l.date_to)
                                THEN 0
                                ELSE (
                                    SELECT
                                        CASE
                                        WHEN (now()::date < l.date_from)
                                        THEN 0
                                        WHEN (l.date_to > l.date_from
                                                AND now()::date < l.date_to)
                                        THEN (
                                            (now()::date - l.date_from)::real /
                                            /* this is not preventing zeroes! */
                                            (l.date_to - l.date_from)::real
                                        )  * l.planned_amount
                                        ELSE l.planned_amount
                                        END
                                )
                            END
                        )) / count(l.id)
                        as theoritical_amount,
                        sum(l.planned_amount) / count(l.id) as planned_amount,
                        /* Practical amount */
                        SUM(analine.amount)
                        as practical_amount,
                        l.general_budget_id as general_budget_id
        """
        return select_str

    def _from(self):
        """
        Helper Method to construct a from statement for the sql view
        l: The budget line (crossovered_budget_lines).
        c: the budget, (crossovered_budget) (sustituye a s)
        a: account_analytic_account
        p: account_budget_post, the general budget
        """
        from_str = """
        crossovered_budget_lines l
                join crossovered_budget c on (l.crossovered_budget_id=c.id)
                    LEFT JOIN
                        account_analytic_account a on (l.analytic_account_id=a.id OR l.analytic_account_id=a.parent_id)
                    left join
                    account_budget_post p on (l.general_budget_id=p.id)
                    LEFT JOIN
                        account_analytic_line analine
                        on (analine.account_id=a.id
                            AND (analine.date between l.date_from AND l.date_to)
                            AND analine.general_account_id=ANY(
                                SELECT DISTINCT acc.id FROM account_account acc
                                INNER JOIN
                                        account_budget_rel rel
                                    ON  rel.account_id = acc.id
                                    INNER JOIN account_budget_post bud
                                    ON rel.budget_id = bud.id
                                    WHERE bud.id=l.general_budget_id
                                            /* TODO: query to get child accounts */
                                            /*
                                            SELECT id FROM account_account
                                                WHERE parent_left >= cuenta.parent_left
                                                AND parent_right <= cuenta.parent_right
                                            */
                                /* TODO: get consolidated accounts */
                            )
                        )

        """
        return from_str

    def _group_by(self):
        """
        Helper Method to generate the sql group_by string
        """
        group_by_str = """
            GROUP BY l.crossovered_budget_id,
                    l.analytic_account_id,
                    l.date_to,
                    l.date_from,
                    l.general_budget_id
        """
        return group_by_str

    def init(self, cr):
        # self._table = sale_report
        drop_view_if_exists(cr, self._table)
        cr.execute("""CREATE or REPLACE VIEW %s as (
            %s
            FROM ( %s )
            %s
            )""" % (
                self._table,
                self._select(),
                self._from(),
                self._group_by()))
