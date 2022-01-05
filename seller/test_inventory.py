import logging
import math
import sys
from typing import List
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE, logged, traced

from common import constants
from common.context import DataGenerator
from common.statistical_test import statistical_test
from seller.batch import Batch
from seller.inventory import Inventory


@traced
@logged
class TestInventory(TestCase):
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
        self.inventory = Inventory.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        for batch in self.inventory.batches:
            self.assertEqual(batch.product, self.inventory.product)
        for i in range(len(self.inventory.batches) - 1):
            self.assertEqual(self.inventory.batches[i].last_date + 1, self.inventory.batches[i + 1].start_date)
        total_duration = sum([batch.duration for batch in self.inventory.batches])
        self.assertGreaterEqual(total_duration, constants.SIMULATION_DURATION)

    def test_current_batch(self):
        self.assertEqual(self.inventory[constants.START_DATE], self.inventory.batches[0])
        self.assertEqual(self.inventory[self.inventory.batches[0].last_date + 1], self.inventory.batches[1])

    @statistical_test(times=10)
    def test_annual_top_line(self, errors: List[float]):
        self.inventory = Inventory.generate_simulated(self.data_generator)
        expected_sales = self.inventory[
                             constants.START_DATE].sales_velocity() * constants.YEAR * self.inventory.product.price * (
                                 1 - self.inventory[constants.START_DATE].out_of_stock_ratio)
        actual_top_line = self.inventory.annual_top_line(constants.START_DATE)
        diff = abs(actual_top_line / expected_sales - 1)
        errors.append(diff)

    def test_gp_per_day(self):
        self.assertEqual(
            self.inventory[constants.START_DATE].gp_per_day(constants.START_DATE),
            self.inventory.batches[0].gp_per_day(constants.START_DATE))
        self.inventory.batches[0].initiate_new_purchase_order(10000000)
        next_batch_day = self.inventory.batches[0].last_date + 1
        self.assertEqual(
            self.inventory[next_batch_day].gp_per_day(next_batch_day),
            self.inventory.batches[1].gp_per_day(next_batch_day))

    def test_revenue_per_day(self):
        self.assertEqual(
            self.inventory[constants.START_DATE].revenue_per_day(constants.START_DATE),
            self.inventory.batches[0].revenue_per_day(constants.START_DATE))
        self.inventory.batches[0].initiate_new_purchase_order(10000000)
        next_batch_day = self.inventory.batches[0].last_date + 1
        self.assertEqual(
            self.inventory[next_batch_day].revenue_per_day(next_batch_day),
            self.inventory.batches[1].revenue_per_day(next_batch_day))

    def test_current_inventory_valuation(self):
        batch: Batch = self.inventory[constants.START_DATE]
        batch.remaining_stock = MagicMock(side_effect=[10, 5])
        batch.sales_velocity = MagicMock(return_value=5)
        batch.product.price = 2
        self.assertAlmostEqual(
            self.inventory.current_inventory_valuation(constants.START_DATE),
            10 + 10 * constants.INVENTORY_NPV_DISCOUNT_FACTOR)
        self.assertAlmostEqual(self.inventory.current_inventory_valuation(constants.START_DATE + 1), 10)

    def test_purhcase_order_valuation(self):
        batch: Batch = self.inventory[constants.START_DATE]
        batch.initiate_new_purchase_order(1000000)
        velocity = 4
        batch.purchase_order.stock = 2 * velocity
        batch.last_date = 2
        batch.sales_velocity = MagicMock(return_value=velocity)
        batch.product.price = 1
        dv = batch.product.price * velocity
        r = constants.INVENTORY_NPV_DISCOUNT_FACTOR
        self.assertAlmostEqual(
            self.inventory.purchase_order_valuation(constants.START_DATE), dv * math.pow(r, 2) + dv * math.pow(r, 3))
        self.assertAlmostEqual(
            self.inventory.purchase_order_valuation(constants.START_DATE + 1),
            dv * math.pow(r, 1) + dv * math.pow(r, 2))

    def test_valuation(self):
        day = constants.START_DATE
        self.data_generator.include_purchase_order_in_valuation = False
        self.assertAlmostEqual(self.inventory.valuation(day), self.inventory.current_inventory_valuation(day))
        self.data_generator.include_purchase_order_in_valuation = True
        self.assertAlmostEqual(
            self.inventory.valuation(day), self.inventory.current_inventory_valuation(
                day) + self.inventory.purchase_order_valuation(day))

    def test_num_batches(self):
        self.data_generator.remove_randomness()
        self.data_generator.inventory_turnover_ratio_median = 5
        self.inventory = Inventory.generate_simulated(self.data_generator)
        total_duration = sum([batch.duration for batch in self.inventory.batches])
        self.assertEqual(total_duration, constants.SIMULATION_DURATION)
        self.assertEqual(
            len(self.inventory.batches),
            self.data_generator.inventory_turnover_ratio_median * constants.YEAR / constants.SIMULATION_DURATION)

    def test_discounted_inventory_value(self):
        r = constants.INVENTORY_NPV_DISCOUNT_FACTOR
        self.assertAlmostEqual(Inventory.discounted_inventory_value(2, 2), 1 + r)
        self.assertAlmostEqual(Inventory.discounted_inventory_value(9, 3), 3 + 3 * r + 3 * r * r)
