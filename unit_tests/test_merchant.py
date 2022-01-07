import logging
import sys
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE

from common import constants
from common.context import DataGenerator
from seller.batch import PurchaseOrder
from seller.merchant import Merchant


class TestMerchant(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=TRACE if sys.gettrace() else logging.WARNING, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = min(self.data_generator.num_products, self.data_generator.max_num_products)
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
        self.assertEqual(self.merchant.annual_top_line(constants.START_DATE), len(self.merchant.inventories))

    def test_is_suspended(self):
        self.merchant.suspension_start_date = None
        self.assertFalse(self.merchant.is_suspended(constants.START_DATE))
        self.merchant.suspension_start_date = constants.START_DATE + 1
        self.assertFalse(self.merchant.is_suspended(constants.START_DATE))
        self.assertTrue(self.merchant.is_suspended(constants.START_DATE + 1))
        self.assertTrue(
            self.merchant.is_suspended(constants.START_DATE + self.data_generator.account_suspension_duration))
        self.assertFalse(
            self.merchant.is_suspended(constants.START_DATE + self.data_generator.account_suspension_duration + 1))

    def test_gp_per_day(self):
        for inventory in self.merchant.inventories:
            inventory.gp_per_day = MagicMock(return_value=1)
        self.merchant.is_suspended = MagicMock(return_value=True)
        self.assertEqual(self.merchant.gp_per_day(constants.START_DATE), 0)
        self.merchant.is_suspended = MagicMock(return_value=False)
        self.assertEqual(self.merchant.gp_per_day(constants.START_DATE), len(self.merchant.inventories))

    def test_revenue_per_day(self):
        for inventory in self.merchant.inventories:
            inventory.revenue_per_day = MagicMock(return_value=1)
        self.merchant.is_suspended = MagicMock(return_value=True)
        self.assertEqual(self.merchant.revenue_per_day(constants.START_DATE), 0)
        self.merchant.is_suspended = MagicMock(return_value=False)
        self.assertEqual(self.merchant.revenue_per_day(constants.START_DATE), len(self.merchant.inventories))

    def test_max_inventory_cost(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].max_cash_needed = MagicMock(return_value=1)
        self.assertEqual(self.merchant.max_cash_needed(constants.START_DATE), len(self.merchant.inventories))

    def test_inventory_cost(self):
        self.data_generator.remove_randomness()
        day = constants.START_DATE
        for day in range(constants.START_DATE, self.data_generator.simulated_duration):
            if max([inventory[day].max_cash_needed(day) for inventory in self.merchant.inventories]) > 0:
                break
        cash = sum([inventory[day].max_cash_needed(day) for inventory in self.merchant.inventories])
        max_spend = self.merchant.inventory_cost(day, cash)
        self.merchant.committed_purchase_orders = MagicMock(return_value=1)
        self.assertLess(self.merchant.inventory_cost(day, cash), max_spend)

    def test_committed_purchase_orders(self):
        day = constants.START_DATE
        for day in range(constants.START_DATE, self.data_generator.simulated_duration):
            if max([inventory[day].max_cash_needed(day) for inventory in self.merchant.inventories]) > 0:
                break
        for inventory in self.merchant.inventories:
            self.assertIsNone(inventory[day].purchase_order)
        self.assertEqual(self.merchant.committed_purchase_orders(day), 0)
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].purchase_order = PurchaseOrder(1, 1, 1)
        self.assertAlmostEqual(
            self.merchant.committed_purchase_orders(constants.START_DATE), len(self.merchant.inventories))

    def test_has_future_revenue(self):
        self.assertTrue(self.merchant.has_future_revenue(constants.START_DATE))
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].has_future_revenue = MagicMock(return_value=False)
        self.assertFalse(self.merchant.has_future_revenue(constants.START_DATE))
        self.merchant.inventories[-1][constants.START_DATE].has_future_revenue.return_value = True
        self.assertTrue(self.merchant.has_future_revenue(constants.START_DATE))

    def test_valuation(self):
        for inventory in self.merchant.inventories:
            inventory.valuation = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.valuation(constants.START_DATE, 0.5), 0.5 + len(self.merchant.inventories))

    def test_inventory_value(self):
        for inventory in self.merchant.inventories:
            inventory.current_inventory_valuation = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.inventory_value(constants.START_DATE), len(self.merchant.inventories))

    def test_organic_rate(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].organic_rate = 0.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.organic_rate(constants.START_DATE), 0.2)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].organic_rate = 0.5
        self.assertGreater(self.merchant.organic_rate(constants.START_DATE), 0.2)

    def test_out_of_stock(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].out_of_stock_rate = 0.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.out_of_stock_rate(constants.START_DATE), 0.2)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].out_of_stock_rate = 0.5
        self.assertGreater(self.merchant.out_of_stock_rate(constants.START_DATE), 0.2)

    def test_profit_margin(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].profit_margin = MagicMock(return_value=0.1)
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.profit_margin(constants.START_DATE), 0.1)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].profit_margin.return_value = 0.2
        self.assertGreater(self.merchant.profit_margin(constants.START_DATE), 0.1)

    def test_inventory_turnover_ratio(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].inventory_turnover_ratio = 3
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.inventory_turnover_ratio(constants.START_DATE), 3)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].inventory_turnover_ratio = 6
        self.assertGreater(self.merchant.inventory_turnover_ratio(constants.START_DATE), 3)

    def test_roas(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].roas = 2.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.roas(constants.START_DATE), 2.2)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].roas = 3.5
        self.assertGreater(self.merchant.roas(constants.START_DATE), 2.2)
