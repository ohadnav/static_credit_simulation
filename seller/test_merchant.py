import logging
import sys
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE

from common import constants
from common.context import DataGenerator
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
            level=TRACE, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.merchant = Merchant.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        self.data_generator.normal_ratio = MagicMock(return_value=1.1)
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.assertEqual(len(self.merchant.inventories), self.data_generator.num_products * 1.1)
        self.assertAlmostEqual(
            self.merchant.account_suspension_chance, self.data_generator.account_suspension_chance * 1.1)

    def test_calculate_suspension_start_date(self):
        constants.SIMULATION_DURATION = 4
        self.data_generator.random = MagicMock(
            side_effect=[constants.NO_VOLATILITY] * 3 + [1 - constants.NO_VOLATILITY])
        self.assertEqual(self.merchant.calculate_suspension_start_date(), constants.START_DATE + 3)
        self.data_generator.random = MagicMock(side_effect=[constants.NO_VOLATILITY] * constants.SIMULATION_DURATION)
        self.assertIsNone(self.merchant.calculate_suspension_start_date())

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
            inventory[constants.START_DATE].max_inventory_cost = MagicMock(return_value=1)
        self.assertEqual(self.merchant.max_inventory_cost(constants.START_DATE), len(self.merchant.inventories))

    def test_inventory_cost(self):
        def new_cost_func(day, cash):
            return 1 if cash > 0 else 0

        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].inventory_cost = new_cost_func
        self.assertEqual(
            self.merchant.inventory_cost(constants.START_DATE, len(self.merchant.inventories)),
            len(self.merchant.inventories))
        self.assertEqual(
            self.merchant.inventory_cost(constants.START_DATE, len(self.merchant.inventories) - 1),
            len(self.merchant.inventories) - 1)

    def test_valuation(self):
        for inventory in self.merchant.inventories:
            inventory.valuation = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.valuation(constants.START_DATE, 0.5), 0.5 + len(self.merchant.inventories))

    def test_inventory_value(self):
        for inventory in self.merchant.inventories:
            inventory.current_inventory_valuation = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.inventory_value(constants.START_DATE), len(self.merchant.inventories))

    def test_organic_ratio(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].organic_ratio = 0.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.organic_ratio(constants.START_DATE), 0.2)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].organic_ratio = 0.5
        self.assertGreater(self.merchant.organic_ratio(constants.START_DATE), 0.2)

    def test_out_of_stock(self):
        for inventory in self.merchant.inventories:
            inventory[constants.START_DATE].out_of_stock_ratio = 0.2
            inventory.annual_top_line = MagicMock(return_value=1)
        self.assertAlmostEqual(self.merchant.out_of_stock_ratio(constants.START_DATE), 0.2)
        self.merchant.inventories[0].annual_top_line.return_value = 10
        self.merchant.inventories[0][constants.START_DATE].out_of_stock_ratio = 0.5
        self.assertGreater(self.merchant.out_of_stock_ratio(constants.START_DATE), 0.2)

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