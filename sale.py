# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard
from trytond.modules.product import round_price

__all__ = ['Sale', 'RecomputePriceStart', 'RecomputePrice']


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._buttons.update({
                'recompute_price': {
                    'invisible': ~Eval('state').in_(['draft', 'quotation']),
                    'icon': 'tryton-refresh',
                    },
                })

    @classmethod
    @ModelView.button_action('sale_recompute_price.wizard_recompute_price')
    def recompute_price(cls, sales):
        pass

    def _recompute_price_by_factor(self, line, factor):
        new_unit_price = round_price(Decimal(line.unit_price * factor))
        values = {
            'unit_price': new_unit_price,
            }
        # Compatibility with sale_discount module
        if hasattr(line, 'gross_unit_price'):
            digits = line.__class__.gross_unit_price.digits[1]
            new_gross_unit_price = round_price(Decimal((line.gross_unit_price * factor)))
            values['gross_unit_price'] = new_gross_unit_price
        return values

    @classmethod
    def recompute_price_by_percentage(cls, sales, percentage):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        to_write = []
        factor = Decimal(1) + Decimal(percentage)
        for sale in sales:
            for line in sale.lines:
                if line.type != 'line':
                    continue
                new_values = sale._recompute_price_by_factor(line, factor)
                if new_values:
                    to_write.extend(([line], new_values))
        if to_write:
            SaleLine.write(*to_write)

    @classmethod
    def recompute_price_by_fixed_amount(cls, sales, amount, currency):
        pool = Pool()
        Currency = pool.get('currency.currency')
        SaleLine = pool.get('sale.line')
        to_write = []
        for sale in sales:
            currency_amount = amount
            if sale.currency != sale.currency:
                currency_amount = Currency.compute(currency, amount,
                    sale.currency)
            if not currency_amount:
                factor = 0.0
            else:
                factor = currency_amount / sale.untaxed_amount
            for line in sale.lines:
                if line.type != 'line':
                    continue
                new_values = sale._recompute_price_by_factor(line, factor)
                if new_values:
                    to_write.extend(([line], new_values))
        if to_write:
            SaleLine.write(*to_write)


class RecomputePriceStart(ModelView):
    'Recompute Price - Start'
    __name__ = 'sale.recompute_price.start'

    method = fields.Selection([
            ('percentage', 'By Percentage'),
            ('fixed_amount', 'Fixed Amount'),
            ], 'Recompute Method', required=True)
    percentage = fields.Float('Percentage', digits=(16, 4),
        states={
            'invisible': Eval('method') != 'percentage',
            'required': Eval('method') == 'percentage',
            },
        depends=['method'])
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        states={
            'invisible': Eval('method') != 'fixed_amount',
            'required': Eval('method') == 'fixed_amount',
            },
        depends=['method', 'currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'invisible': Eval('method') != 'fixed_amount',
            'required': Eval('method') == 'fixed_amount',
            },
        depends=['method'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @staticmethod
    def default_method():
        return 'percentage'


class RecomputePrice(Wizard):
    'Recompute Sale Price'
    __name__ = 'sale.recompute_price'

    start = StateView('sale.recompute_price.start',
        'sale_recompute_price.recompute_price_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Recompute', 'compute', 'tryton-ok', default=True),
            ])
    compute = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Sale = pool.get('sale.sale')
        default = {}
        if len(Transaction().context['active_ids']) == 1:
            sale = Sale(Transaction().context['active_id'])
            default['currency'] = sale.currency.id
            default['currency_digits'] = sale.currency.digits
            default['amount'] = (sale.untaxed_amount)
        return default

    def get_additional_args(self):
        method_name = 'get_additional_args_%s' % self.start.method
        if not hasattr(self, method_name):
            return {}
        return getattr(self, method_name)()

    def get_additional_args_percentage(self):
        return {
            'percentage': self.start.percentage,
            }

    def get_additional_args_fixed_amount(self):
        return {
            'amount': self.start.amount,
            'currency': self.start.currency,
            }

    def transition_compute(self):
        pool = Pool()
        Sale = pool.get('sale.sale')

        method_name = 'recompute_price_by_%s' % self.start.method
        method = getattr(Sale, method_name)
        if method:
            method(Sale.browse(Transaction().context.get('active_ids')),
                **self.get_additional_args())
        return 'end'
