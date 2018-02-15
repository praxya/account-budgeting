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

    def _prac_amt(self, cr, uid, ids, context=None):
        res = {}
        result = 0.0
        if context is None:
            context = {}
        account_obj = self.pool.get('account.account')
        for line in self.browse(cr, uid, ids, context=context):
            acc_ids = [x.id for x in line.general_budget_id.account_ids]
            if not acc_ids:
                raise osv.except_osv(
                    _('Error!'),
                    _("The Budget '%s' has no accounts!") % ustr(
                        line.general_budget_id.name))
            acc_ids = account_obj._get_children_and_consol(
                cr, uid, acc_ids, context=context)
            date_to = line.date_to
            date_from = line.date_from
            if line.analytic_account_id.id:
                cr.execute(
                    """
                    SELECT SUM(amount)
                    FROM account_analytic_line
                    WHERE account_id=%s
                    AND (date
                       between to_date(%s,'yyyy-mm-dd')
                    AND to_date(%s,'yyyy-mm-dd')) AND
                       general_account_id=ANY(%s)
                    """,
                    (line.analytic_account_id.id, date_from, date_to, acc_ids,))
                result = cr.fetchone()[0]
            if result is None:
                result = 0.00
            res[line.id] = result
        return res

    def _prac(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._prac_amt(
                cr, uid, [line.id], context=context)[line.id]
        return res

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
        'paid_date': fields.date('Paid Date', readonly=True),
        'planned_amount': fields.float('Planned Amount', readonly=True,),
        'theoritical_amount': fields.float('Theoretical Amount', readonly=True),
        'practical_amount': fields.float(
            'Practical Amount',
            readonly=True
        ),
        # Function fields
        'percentage': fields.function(
            _perc,
            string='Percentage',
            type='float',
        ),
    }
    _order = 'crossovered_budget_id desc'

    # obfuscated variables in the examples below:
    # r: res_currency_rate
    # l: sale_order_line
    # s: sale_order
    # t: product_template

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
                        ))
                        as theoritical_amount,
                        /*  VERY SLOW LOADING PROBLEM */
                        /* Practical amount */
                        SUM((
                        SELECT amount
                            FROM account_analytic_line
                            WHERE account_id=l.analytic_account_id
                            AND (date between l.date_from AND l.date_to)
                            AND general_account_id=ANY(
                                WITH cuenta AS (
                                    SELECT * FROM account_account
                                    WHERE id=ANY(
                                        SELECT account_id
                                        FROM account_budget_rel
                                        WHERE budget_id=l.general_budget_id
                                    )
                                )
                                SELECT id FROM account_account
                                /* query to get child accounts */
                                    WHERE parent_left >= cuenta.parent_left
                                    AND parent_right <= cuenta.parent_right
                                /* TODO: get consolidated accounts */
                            )
                        ))
                        as practical_amount,
                        l.general_budget_id as general_budget_id,
                        sum(l.planned_amount) as planned_amount
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
                /* Please review this! */
                    /* Why do we need the analytic account table ?
                    left join
                        account_analytic_account a on (l.analytic_account_id=a.id)
                    */
                /* Beginning of the join added before the
                    SLOW loading problem */
                    /*
                LEFT JOIN
                    */
                    left join
                    account_budget_post p on (l.general_budget_id=p.id)
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
