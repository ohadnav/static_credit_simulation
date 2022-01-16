from unittest.mock import MagicMock

from common import constants
from common.numbers import Float, Dollar, ONE, Date, Stock
from seller.batch import PurchaseOrder, Batch
from seller.inventory import Inventory
from seller.merchant import Merchant
from seller.product import Product
from tests.util_test import BaseTestCase


class TestMerchant(BaseTestCase):
    def setUp(self) -> None:
        super(TestMerchant, self).setUp()
        self.data_generator.max_num_products = 4
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        self.data_generator.normal_ratio = MagicMock(return_value=1.1)
        self.data_generator.random = MagicMock(return_value=constants.NO_VOLATILITY)
        self.data_generator.max_num_products = 11
        self.data_generator.num_products = 10
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.assertEqual(len(self.merchant.inventories), self.data_generator.num_products * 1.1)
        self.assertIsNone(self.merchant.suspension_start_date)
        self.data_generator.random = MagicMock(return_value=1 - constants.NO_VOLATILITY)
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.assertIsNotNone(self.merchant.suspension_start_date)

    def test_annual_top_line(self):
        for inventory in self.merchant.inventories:
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertEqual(self.merchant.annual_top_line(self.data_generator.start_date), len(self.merchant.inventories))

    def test_is_suspended(self):
        self.merchant.suspension_start_date = None
        self.assertFalse(self.merchant.is_suspended(self.data_generator.start_date))
        self.merchant.suspension_start_date = self.data_generator.start_date + 1
        self.assertFalse(self.merchant.is_suspended(self.data_generator.start_date))
        self.assertTrue(self.merchant.is_suspended(self.data_generator.start_date + 1))
        self.assertTrue(
            self.merchant.is_suspended(
                self.data_generator.start_date + self.data_generator.account_suspension_duration))
        self.assertFalse(
            self.merchant.is_suspended(
                self.data_generator.start_date + self.data_generator.account_suspension_duration + 1))

    def test_gp_per_day(self):
        for inventory in self.merchant.inventories:
            inventory.gp_per_day = MagicMock(return_value=1)
        self.merchant.is_suspended = MagicMock(return_value=True)
        self.assertEqual(self.merchant.gp_per_day(self.data_generator.start_date), 0)
        self.merchant.is_suspended = MagicMock(return_value=False)
        self.assertEqual(self.merchant.gp_per_day(self.data_generator.start_date), len(self.merchant.inventories))

    def test_revenue_per_day(self):
        for inventory in self.merchant.inventories:
            inventory.revenue_per_day = MagicMock(return_value=1)
        self.merchant.is_suspended = MagicMock(return_value=True)
        self.assertEqual(self.merchant.revenue_per_day(self.data_generator.start_date), 0)
        self.merchant.is_suspended = MagicMock(return_value=False)
        self.assertEqual(self.merchant.revenue_per_day(self.data_generator.start_date), len(self.merchant.inventories))

    def test_max_inventory_cost(self):
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].max_cash_needed = MagicMock(return_value=1)
        self.assertEqual(self.merchant.max_cash_needed(self.data_generator.start_date), len(self.merchant.inventories))

    def test_inventory_cost(self):
        day: Date = self.data_generator.start_date
        for day in range(self.data_generator.start_date, self.data_generator.simulated_duration):
            day = Date(day)
            if Float.max([inventory[day].max_cash_needed(day) for inventory in self.merchant.inventories]) > 0:
                break
        cash = Float.sum([inventory[day].max_cash_needed(day) for inventory in self.merchant.inventories])
        max_spend = self.merchant.inventory_cost(day, cash)
        self.merchant.committed_purchase_orders = MagicMock(return_value=1)
        self.assertLess(self.merchant.inventory_cost(day, cash), max_spend)

    def test_inventory_cost_multiple_PO_same_date(self):
        product = Product.generate_simulated(self.data_generator)
        batch1 = Batch.generate_simulated(self.data_generator, product)
        batch2 = Batch.generate_simulated(self.data_generator, product)
        batch1.get_purchase_order_start_date = MagicMock(return_value=self.data_generator.start_date)
        batch2.get_purchase_order_start_date = MagicMock(return_value=self.data_generator.start_date)
        max_cost = batch1.max_cash_needed(self.data_generator.start_date) + batch2.max_cash_needed(
            self.data_generator.start_date)
        upfront_max_cost = batch1.max_purchase_order().upfront_cost + batch2.max_purchase_order().upfront_cost
        single_max_cost = Float.max(
            batch1.max_cash_needed(self.data_generator.start_date),
            batch2.max_cash_needed(self.data_generator.start_date))
        inventories = [Inventory(self.data_generator, product, [batch1]),
            Inventory(self.data_generator, product, [batch2])]
        self.merchant = Merchant(self.data_generator, inventories, None)
        self.assertLess(self.merchant.inventory_cost(self.data_generator.start_date, single_max_cost), upfront_max_cost)

    def test_committed_purchase_orders(self):
        day = self.data_generator.start_date
        for day in range(self.data_generator.start_date, self.data_generator.simulated_duration):
            day = Date(day)
            if Float.max([inventory[day].max_cash_needed(day) for inventory in self.merchant.inventories]) > 0:
                break
        for inventory in self.merchant.inventories:
            self.assertIsNone(inventory[day].purchase_order)
        self.assertEqual(self.merchant.committed_purchase_orders(day), 0)
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].purchase_order = PurchaseOrder(Stock(1), ONE, ONE)
        self.assertAlmostEqual(
            self.merchant.committed_purchase_orders(self.data_generator.start_date), len(self.merchant.inventories))

    def test_has_future_revenue(self):
        self.assertTrue(self.merchant.has_future_revenue(self.data_generator.start_date))
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].has_future_revenue = MagicMock(return_value=False)
        self.assertFalse(self.merchant.has_future_revenue(self.data_generator.start_date))
        self.merchant.inventories[-1][self.data_generator.start_date].has_future_revenue = MagicMock(return_value=True)
        self.assertTrue(self.merchant.has_future_revenue(self.data_generator.start_date))

    def test_valuation(self):
        for inventory in self.merchant.inventories:
            inventory.valuation = MagicMock(return_value=1)
        net_cashflow = Dollar(0.5)
        self.assertAlmostEqual(
            self.merchant.valuation(self.data_generator.start_date, net_cashflow),
            net_cashflow + len(self.merchant.inventories))

    def test_inventory_value(self):
        for inventory in self.merchant.inventories:
            inventory.current_inventory_valuation = MagicMock(return_value=1)
        self.assertAlmostEqual(
            self.merchant.inventory_value(self.data_generator.start_date), len(self.merchant.inventories))

    def test_organic_rate(self):
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].organic_rate = 0.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.organic_rate(self.data_generator.start_date), 0.2)
        self.merchant.inventories[0].annual_top_line = MagicMock(return_value=10)
        self.merchant.inventories[0][self.data_generator.start_date].organic_rate = 0.5
        self.assertGreater(self.merchant.organic_rate(self.data_generator.start_date), 0.2)

    def test_out_of_stock(self):
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].out_of_stock_rate = 0.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.out_of_stock_rate(self.data_generator.start_date), 0.2)
        self.merchant.inventories[0].annual_top_line = MagicMock(return_value=10)
        self.merchant.inventories[0][self.data_generator.start_date].out_of_stock_rate = 0.5
        self.assertGreater(self.merchant.out_of_stock_rate(self.data_generator.start_date), 0.2)

    def test_profit_margin(self):
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].profit_margin = MagicMock(return_value=0.1)
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.profit_margin(self.data_generator.start_date), 0.1)
        self.merchant.inventories[0].annual_top_line = MagicMock(return_value=10)
        self.merchant.inventories[0][self.data_generator.start_date].profit_margin = MagicMock(return_value=0.2)
        self.assertGreater(self.merchant.profit_margin(self.data_generator.start_date), 0.1)

    def test_inventory_turnover_ratio(self):
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].inventory_turnover_ratio = 3
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.inventory_turnover_ratio(self.data_generator.start_date), 3)
        self.merchant.inventories[0].annual_top_line = MagicMock(return_value=10)
        self.merchant.inventories[0][self.data_generator.start_date].inventory_turnover_ratio = 6
        self.assertGreater(self.merchant.inventory_turnover_ratio(self.data_generator.start_date), 3)

    def test_roas(self):
        for inventory in self.merchant.inventories:
            inventory[self.data_generator.start_date].roas = 2.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.roas(self.data_generator.start_date), 2.2)
        self.merchant.inventories[0].annual_top_line = MagicMock(return_value=10)
        self.merchant.inventories[0][self.data_generator.start_date].roas = 3.5
        self.assertGreater(self.merchant.roas(self.data_generator.start_date), 2.2)
