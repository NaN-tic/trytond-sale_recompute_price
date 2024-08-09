import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install sale
        config = activate_modules('sale_recompute_price')

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        Group = Model.get('res.group')
        config._context = User.get_preferences(True, config.context)

        # Create sale user
        sale_user = User()
        sale_user.name = 'Sale'
        sale_user.login = 'sale'
        sale_group, = Group.find([('name', '=', 'Sales')])
        sale_user.groups.append(sale_group)
        sale_user.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create parties
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.salable = True
        template.list_price = Decimal('10')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.save()
        product.template = template
        product.save()
        service = Product()
        template = ProductTemplate()
        template.name = 'service'
        template.default_uom = unit
        template.type = 'service'
        template.salable = True
        template.list_price = Decimal('100')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.save()
        service.template = template
        service.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create a sale and apply a discount of 10%
        config.user = sale_user.id
        Sale = Model.get('sale.sale')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.invoice_method = 'order'
        sale_line = sale.lines.new()
        sale_line.product = product
        sale_line.quantity = 1.0
        sale_line = sale.lines.new()
        sale_line.product = service
        sale_line.quantity = 1.0
        sale_line = sale.lines.new()
        sale_line.type = 'comment'
        sale_line.description = 'Comment'
        sale.click('quote')
        self.assertEqual(sale.untaxed_amount, Decimal('110.00'))

        recompute = Wizard('sale.recompute_price', [sale])
        recompute.form.method = 'percentage'
        recompute.form.percentage = -0.1
        recompute.execute('compute')
        sale.reload()
        self.assertEqual(sale.untaxed_amount, Decimal('99.00'))

        product_line, service_line, _ = sale.lines
        self.assertEqual(product_line.unit_price, Decimal('9.0000'))
        self.assertEqual(service_line.unit_price, Decimal('90.0000'))

        # Now we increase the price 5%
        recompute = Wizard('sale.recompute_price', [sale])
        recompute.form.method = 'percentage'
        recompute.form.percentage = 0.05
        recompute.execute('compute')
        sale.reload()
        self.assertEqual(sale.untaxed_amount, Decimal('103.95'))

        product_line, service_line, _ = sale.lines
        self.assertEqual(product_line.unit_price, Decimal('9.4500'))
        self.assertEqual(service_line.unit_price, Decimal('94.5000'))

        # Now we change it to a fixed amount
        recompute = Wizard('sale.recompute_price', [sale])
        recompute.form.method = 'fixed_amount'
        recompute.form.amount = Decimal('110.00')
        recompute.execute('compute')
        sale.reload()
        self.assertEqual(sale.untaxed_amount, Decimal('110.00'))

        product_line, service_line, _ = sale.lines
        self.assertEqual(product_line.unit_price, Decimal('10.0000'))
        self.assertEqual(service_line.unit_price, Decimal('100.0000'))

        # Change it to a different amount
        recompute = Wizard('sale.recompute_price', [sale])
        recompute.form.method = 'fixed_amount'
        recompute.form.amount = Decimal('60.00')
        recompute.execute('compute')
        sale.reload()
        self.assertEqual(sale.untaxed_amount, Decimal('60.00'))

        product_line, service_line, _ = sale.lines
        self.assertEqual(product_line.unit_price, Decimal('5.4545'))
        self.assertEqual(service_line.unit_price, Decimal('54.5455'))
