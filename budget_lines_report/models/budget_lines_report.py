# -*- coding: utf-8 -*-
from datetime import date, datetime
from openerp.tools import drop_view_if_exists, ustr, DEFAULT_SERVER_DATE_FORMAT
from openerp.osv import fields, osv

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------
def strToDate(dt):
    return date(int(dt[0:4]), int(dt[5:7]), int(dt[8:10]))

def strToDatetime(strdate):
    return datetime.strptime(strdate, DEFAULT_SERVER_DATE_FORMAT)


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
                raise osv.except_osv(_('Error!'),_("The Budget '%s' has no accounts!") % ustr(line.general_budget_id.name))
            acc_ids = account_obj._get_children_and_consol(cr, uid, acc_ids, context=context)
            date_to = line.date_to
            date_from = line.date_from
            if line.analytic_account_id.id:
                cr.execute("SELECT SUM(amount) FROM account_analytic_line WHERE account_id=%s AND (date "
                       "between to_date(%s,'yyyy-mm-dd') AND to_date(%s,'yyyy-mm-dd')) AND "
                       "general_account_id=ANY(%s)", (line.analytic_account_id.id, date_from, date_to,acc_ids,))
                result = cr.fetchone()[0]
            if result is None:
                result = 0.00
            res[line.id] = result
        return res

    def _prac(self, cr, uid, ids, name, args, context=None):
        res={}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._prac_amt(cr, uid, [line.id], context=context)[line.id]
        return res

    def _theo_amt(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            today = datetime.now()

            if line.paid_date:
                if strToDate(line.date_to) <= strToDate(line.paid_date):
                    theo_amt = 0.00
                else:
                    theo_amt = line.planned_amount
            else:
                line_timedelta = strToDatetime(line.date_to) - strToDatetime(line.date_from)
                elapsed_timedelta = today - (strToDatetime(line.date_from))

                if elapsed_timedelta.days < 0:
                    # If the budget line has not started yet, theoretical amount should be zero
                    theo_amt = 0.00
                elif line_timedelta.days > 0 and today < strToDatetime(line.date_to):
                    # If today is between the budget line date_from and date_to
                    theo_amt = (elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()) * line.planned_amount
                else:
                    theo_amt = line.planned_amount

            res[line.id] = theo_amt
        return res

    def _theo(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._theo_amt(cr, uid, [line.id], context=context)[line.id]
        return res

    def _perc(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.theoritical_amount <> 0.00:
                res[line.id] = float((line.practical_amount or 0.0) / line.theoritical_amount) * 100
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
        'planned_amount':fields.float('Planned Amount', readonly=True,
                                      # digits_compute=dp.get_precision('Account')
        ),
        # Function fields
        'practical_amount':fields.function(
            _prac,
            string='Practical Amount',
            type='float',
            # digits_compute=dp.get_precision('Account'),
        ),
        'theoritical_amount':fields.function(
            _theo,
            string='Theoretical Amount',
            type='float',
            # digits_compute=dp.get_precision('Account'),
        ),
        'percentage':fields.function(
            _perc,
            string='Percentage',
            type='float',
        ),
        'company_id': fields.related(
            'crossovered_budget_id',
            'company_id', type='many2one',
            relation='res.company',
            string='Company',
            store=True,
            readonly=True,
        )

        # Example fields used for a sale report:
        # 'date': fields.datetime('Date Order', readonly=True),  # TDE FIXME master: rename into date_order
        # 'date_confirm': fields.date('Date Confirm', readonly=True),
        # 'product_id': fields.many2one('product.product', 'Product', readonly=True),
        # 'product_uom': fields.many2one('product.uom', 'Unit of Measure', readonly=True),
        # 'product_uom_qty': fields.float('# of Qty', readonly=True),
        # 'partner_id': fields.many2one('res.partner', 'Partner', readonly=True),
        # 'company_id': fields.many2one('res.company', 'Company', readonly=True),
        # 'order_id': fields.many2one('sale.order', 'Pedido venta', readonly=True),
        # 'user_id': fields.many2one('res.users', 'Salesperson', readonly=True),
        # 'price_total': fields.float('Total Price', readonly=True),
        # 'commitment_delay': fields.float('Retraso compromisos', digits=(16,2), readonly=True),
        # 'categ_id': fields.many2one('product.category','Category of Product', readonly=True),
        # 'nbr': fields.integer('# of Lines', readonly=True),  # TDE FIXME master: rename into nbr_lines
        # 'state': fields.selection([
            # ('cancel', 'Cancelled'),
            # ('draft', 'Draft'),
            # ('confirmed', 'Confirmed'),
            # ('exception', 'Exception'),
            # ('done', 'Done')], 'Order Status', readonly=True),
        # 'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', readonly=True),
        # 'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account', readonly=True),
        # 'section_id': fields.many2one('crm.case.section', 'Sales Team'),
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
        # TODO: add currency rates, not included in the main account_budget:
        # """
            # WITH currency_rate (currency_id, rate, date_start, date_end) AS (
                    # SELECT r.currency_id, r.rate, r.name AS date_start,
                        # (SELECT name FROM res_currency_rate r2
                        # WHERE r2.name > r.name AND
                            # r2.currency_id = r.currency_id
                         # ORDER BY r2.name ASC
                         # LIMIT 1) AS date_end
                    # FROM res_currency_rate r
                # )
        # """
        # The join for currency could be based on this one:
        # """
                    # join currency_rate cr on (cr.currency_id = pp.currency_id and
                        # cr.date_start <= coalesce(s.date_order, now()) and
                        # (cr.date_end is null or cr.date_end > coalesce(s.date_order, now())))
        # """

        # Ejemplo de select str del que parto:

        """
             SELECT min(l.id) as id,
                    l.product_id as product_id,
                    t.uom_id as product_uom,
                    sum(l.product_uom_qty / u.factor * u2.factor) as product_uom_qty,
                    sum(l.product_uom_qty * l.price_unit / cr.rate * (100.0-l.discount) / 100.0) as price_total,
                    count(*) as nbr,
                    s.date_order as date,
                    s.date_confirm as date_confirm,
                    s.partner_id as partner_id,
                    s.user_id as user_id,
                    s.company_id as company_id,
                    s.id as order_id,
                    (SELECT CASE
                        WHEN extract(epoch from avg(date_trunc('day',s.last_effective_date)-date_trunc('day',s.commitment_date1)))/(24*60*60)::decimal(16,2) > 0
                            THEN extract(epoch from avg(date_trunc('day',s.last_effective_date)-date_trunc('day',s.commitment_date1)))/(24*60*60)::decimal(16,2) / (SELECT count(*) from sale_order_line sol where sol.order_id = s.id)
                            ELSE 0
                        END AS commitment_delay),
                    l.state,
                    t.categ_id as categ_id,
                    s.pricelist_id as pricelist_id,
                    s.project_id as analytic_account_id,
                    s.section_id as section_id
        """

        select_str = """
                SELECT min(l.id) as id,
                       l.crossovered_budget_id,
                       l.date_to,
                       l.date_from
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
                        left join account_analytic_account a on (l.analytic_account_id=a.id)
                            left join account_budget_post p on (l.general_budget_id=p.id)
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
                    l.date_from
        """
        return group_by_str

    def init(self, cr):
        # self._table = sale_report
        drop_view_if_exists(cr, self._table)
        cr.execute("""CREATE or REPLACE VIEW %s as (
            %s
            FROM ( %s )
            %s
            )""" % (self._table, self._select(), self._from(), self._group_by()))
