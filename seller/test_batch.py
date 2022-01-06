import logging
import sys
from random import randint
from typing import List, Tuple, Any
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE, traced, logged

from common import constants
from common.context import DataGenerator
from common.statistical_test import statistical_test_mean_error, statistical_test_bool
from seller.batch import Batch, PurchaseOrder


@traced
@logged
class TestBatch(TestCase):
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
        self.batch: Batch = Batch.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        ratio = 1.1
        self.data_generator.normal_ratio = MagicMock(return_value=ratio)
        self.batch = Batch.generate_simulated(self.data_generator)
        self.assertAlmostEqual(
            self.batch.inventory_turnover_ratio, self.data_generator.inventory_turnover_ratio_median * ratio)
        self.assertAlmostEqual(self.batch.out_of_stock_rate, self.data_generator.out_of_stock_rate_median * ratio)
        self.assertAlmostEqual(self.batch.roas, self.data_generator.roas_median * ratio)
        self.assertAlmostEqual(self.batch.organic_rate, self.data_generator.organic_rate_median * ratio)
        self.assertEqual(self.batch.shipping_duration, int(self.data_generator.shipping_duration_avg * ratio))
        self.assertEqual(
            self.batch.stock,
            int(max(self.batch.lead_time + 1, self.batch.product.min_purchase_order_size) * ratio))
        self.assertEqual(self.batch.start_date, constants.START_DATE)
        self.assertIsNone(self.batch.next_batch)

    def test_generate_simulated_with_previous(self):
        ratio = 1.1
        self.data_generator.normal_ratio = MagicMock(return_value=ratio)
        self.batch = Batch.generate_simulated(self.data_generator)
        batch2 = Batch.generate_simulated(self.data_generator, previous=self.batch)
        self.assertEqual(self.batch.product, batch2.product)
        self.assertAlmostEqual(
            batch2.inventory_turnover_ratio, self.batch.inventory_turnover_ratio * ratio)
        self.assertAlmostEqual(batch2.out_of_stock_rate, self.batch.out_of_stock_rate * ratio)
        self.assertAlmostEqual(batch2.roas, self.batch.roas * ratio)
        self.assertAlmostEqual(batch2.organic_rate, self.batch.organic_rate * ratio)
        self.assertEqual(batch2.stock, 0)
        self.assertEqual(batch2.start_date, self.batch.last_date + 1)

    @statistical_test_bool(num_lists=8)
    def test_generated_makes_sense(self, is_true: List[List[Tuple[bool, Any]]]):
        self.batch = Batch.generate_simulated(self.data_generator)
        is_true[0].append(
            (
                self.data_generator.shipping_duration_avg / 2 < self.batch.shipping_duration < 2 * self.data_generator.shipping_duration_avg,
                self.batch.shipping_duration))
        is_true[1].append((constants.MONTH < self.batch.lead_time < 3 * constants.MONTH, self.batch.lead_time))
        is_true[2].append(
            (
                self.data_generator.inventory_turnover_ratio_median / 2 < self.batch.inventory_turnover_ratio < \
                2 * self.data_generator.inventory_turnover_ratio_median, self.batch.inventory_turnover_ratio))
        is_true[3].append(
            (
                self.data_generator.roas_median / 1.5 < self.batch.roas < \
                1.5 * self.data_generator.roas_median, self.batch.roas))
        is_true[4].append(
            (
                self.data_generator.organic_rate_median / 2 < self.batch.organic_rate < \
                2 * self.data_generator.organic_rate_median, self.batch.organic_rate))
        is_true[5].append(
            (
                constants.MIN_PURCHASE_ORDER_SIZE * 3 < self.batch.stock < constants.MIN_PURCHASE_ORDER_SIZE * 2000,
                self.batch.stock))
        is_true[6].append(
            (0.01 < self.batch.gp_margin() - self.batch.product.cogs_margin < 0.15,
             (round(self.batch.gp_margin(), 2), round(self.batch.product.cogs_margin, 2))))
        is_true[7].append((0.01 < self.batch.profit_margin() < 0.15, round(self.batch.profit_margin(), 2)))

    def test_has_future_revenue(self):
        self.batch.is_out_of_stock = MagicMock(return_value=True)
        self.batch.stock = 0
        self.batch.purchase_order = None
        self.assertFalse(self.batch.has_future_revenue(randint(self.batch.start_date, self.batch.last_date)))
        self.batch.purchase_order = PurchaseOrder(1, 1, 1)
        self.assertTrue(self.batch.has_future_revenue(randint(self.batch.start_date, self.batch.last_date)))
        self.batch.purchase_order = None
        self.batch.stock = 1
        self.assertFalse(self.batch.has_future_revenue(randint(self.batch.start_date, self.batch.last_date)))
        self.batch.is_out_of_stock = MagicMock(return_value=False)
        self.assertTrue(self.batch.has_future_revenue(randint(self.batch.start_date, self.batch.last_date)))
        self.batch.stock = 0
        self.assertFalse(self.batch.has_future_revenue(randint(self.batch.start_date, self.batch.last_date)))

    def test_margins(self):
        self.assertGreater(self.batch.revenue_margin(), self.batch.gp_margin())
        self.assertGreater(self.batch.gp_margin(), self.batch.profit_margin())

    def test_marketing_margin(self):
        self.batch.organic_rate = 1
        self.assertAlmostEqual(self.batch.marketing_margin(), 0)
        self.batch.organic_rate = 0.8
        self.batch.roas = 1
        self.assertAlmostEqual(self.batch.marketing_margin(), 0.2)
        self.batch.roas = 2
        self.assertAlmostEqual(self.batch.marketing_margin(), 0.1)
        self.batch.roas = 1000000
        self.assertLess(self.batch.marketing_margin(), 0.01)

    def test_acos(self):
        self.batch.roas = 2
        self.assertAlmostEqual(self.batch.acos(), self.batch.product.price / 2)

    def test_get_manufacturing_done_date(self):
        self.assertIsNone(self.batch.get_manufacturing_done_date())
        self.batch.purchase_order = PurchaseOrder(0, 0, 0)
        self.batch.get_purchase_order_start_date = MagicMock(return_value=1)
        self.assertEqual(self.batch.get_manufacturing_done_date(), 1 + self.batch.product.manufacturing_duration)

    def test_get_purchase_order_start_date(self):
        self.batch.lead_time = 2
        self.assertEqual(self.batch.get_purchase_order_start_date(), self.batch.last_date - 1)
        self.batch.last_date = 2
        self.assertEqual(self.batch.get_purchase_order_start_date(), 1)

    def test_max_purchase_order(self):
        max_stock = self.batch.max_stock_for_next_purchase_order()
        self.assertEqual(self.batch.max_purchase_order().stock, max_stock)

    def test_initiate_new_purchase_order(self):
        self.data_generator.remove_randomness()
        self.data_generator.conservative_cash_management = False
        batch2 = Batch.generate_simulated(self.data_generator, previous=self.batch)
        upfront, post = self.batch.product.purchase_order_cost(self.batch.product.min_purchase_order_size)
        self.assertIsNone(self.batch.initiate_new_purchase_order(post - 1))
        self.assertIsNotNone(self.batch.initiate_new_purchase_order(post))
        self.assertEqual(
            self.batch.purchase_order, PurchaseOrder(self.batch.product.min_purchase_order_size, upfront, post))
        self.assertEqual(batch2.stock, self.batch.product.min_purchase_order_size)
        upfront2, post2 = self.batch.product.purchase_order_cost(self.batch.max_stock_for_next_purchase_order())
        self.assertIsNotNone(self.batch.initiate_new_purchase_order(post2))
        self.assertEqual(
            self.batch.purchase_order, PurchaseOrder(self.batch.max_stock_for_next_purchase_order(), upfront2, post2))
        self.assertEqual(self.batch.purchase_order.stock, batch2.stock)

    def test_can_afford_purchase_order(self):
        self.data_generator.conservative_cash_management = False
        po = self.batch.max_purchase_order()
        self.assertTrue(self.batch.can_afford_purchase_order(po, po.post_manufacturing_cost))
        self.assertFalse(self.batch.can_afford_purchase_order(po, po.post_manufacturing_cost - 1))
        self.data_generator.conservative_cash_management = True
        self.assertTrue(self.batch.can_afford_purchase_order(po, po.post_manufacturing_cost + po.upfront_cost))
        self.assertFalse(self.batch.can_afford_purchase_order(po, po.post_manufacturing_cost + po.upfront_cost - 1))

    def test_max_inventory_cost(self):
        self.data_generator.remove_randomness()
        self.data_generator.conservative_cash_management = False
        self.assertEqual(self.batch.max_inventory_cost(constants.START_DATE - 1), 0)
        self.assertEqual(
            self.batch.max_inventory_cost(self.batch.get_purchase_order_start_date()),
            self.batch.max_purchase_order().upfront_cost)
        self.assertEqual(
            self.batch.max_inventory_cost(self.batch.get_purchase_order_start_date()),
            self.batch.max_purchase_order().upfront_cost)
        upfront, post = self.batch.product.purchase_order_cost(self.batch.product.min_purchase_order_size)
        self.assertIsNotNone(self.batch.initiate_new_purchase_order(post))
        self.assertEqual(self.batch.max_inventory_cost(self.batch.get_manufacturing_done_date()), post)

    def test_inventory_cost(self):
        self.data_generator.remove_randomness()
        self.data_generator.conservative_cash_management = False
        upfront, post = self.batch.product.purchase_order_cost(self.batch.product.min_purchase_order_size)
        self.assertEqual(self.batch.inventory_cost(self.data_generator.simulated_duration + 1, 1000000), 0)
        self.assertEqual(self.batch.inventory_cost(self.batch.get_purchase_order_start_date(), post - 1), 0)
        self.assertIsNone(self.batch.purchase_order)
        self.assertAlmostEqual(self.batch.inventory_cost(self.batch.get_purchase_order_start_date(), post), upfront)
        self.assertEqual(
            self.batch.purchase_order, PurchaseOrder(self.batch.product.min_purchase_order_size, upfront, post))
        self.assertAlmostEqual(self.batch.inventory_cost(self.batch.get_manufacturing_done_date(), 0), post)

    def test_is_out_of_stock(self):
        self.assertFalse(self.batch.is_out_of_stock(constants.START_DATE))
        self.assertFalse(
            self.batch.is_out_of_stock(constants.START_DATE + self.batch.duration_in_stock() - 1))
        self.assertTrue(self.batch.is_out_of_stock(constants.START_DATE + self.batch.duration_in_stock()))

    @statistical_test_mean_error
    def test_out_of_stock_statistical_test(self, errors):
        count_oos = 0
        self.batch = Batch.generate_simulated(self.data_generator)
        for day in range(self.batch.start_date, self.batch.last_date + 1):
            if self.batch.is_out_of_stock(day):
                count_oos += 1
        oos_error = abs(count_oos / self.batch.duration - self.batch.out_of_stock_rate)
        errors.append(oos_error)

    def test_sales_velocity(self):
        self.batch.stock = 30
        self.batch.duration = 4
        self.batch.out_of_stock_rate = 0.25
        self.assertAlmostEqual(self.batch.sales_velocity(), 10)

    def test_revenue_per_day(self):
        self.assertEqual(self.batch.revenue_per_day(constants.START_DATE + self.batch.duration_in_stock() + 1), 0)
        self.batch.revenue_margin = MagicMock(return_value=1)
        self.assertAlmostEqual(
            self.batch.revenue_per_day(constants.START_DATE), self.batch.product.price * self.batch.sales_velocity())

    def test_revenue_margin(self):
        self.assertGreater(self.batch.revenue_margin(), 0)

    def test_gp_per_day(self):
        self.assertEqual(self.batch.gp_per_day(constants.START_DATE + self.batch.duration_in_stock() + 1), 0)
        self.batch.gp_margin = MagicMock(return_value=0.8)
        self.assertAlmostEqual(
            self.batch.total_revenue_per_day(constants.START_DATE) * 0.8, self.batch.gp_per_day(constants.START_DATE))

    def test_duration_in_stock(self):
        self.batch.out_of_stock_rate = 0
        self.assertEqual(self.batch.duration_in_stock(), self.batch.duration)
        self.batch.stock = 30
        self.batch.sales_velocity = MagicMock(return_value=10)
        self.batch.duration = 4
        self.batch.out_of_stock_rate = 0.25
        self.assertEqual(self.batch.duration_in_stock(), 3)
        self.batch.sales_velocity = MagicMock(return_value=0)
        self.assertEqual(self.batch.duration_in_stock(), self.batch.duration)
        self.batch.stock = 0
        self.assertEqual(self.batch.duration_in_stock(), 0)

    def test_remaining_stock(self):
        self.assertEqual(self.batch.remaining_stock(constants.START_DATE), self.batch.stock)
        self.assertEqual(
            self.batch.remaining_stock(constants.START_DATE + 1), self.batch.stock - int(self.batch.sales_velocity()))
        self.assertGreater(self.batch.remaining_stock(constants.START_DATE + self.batch.duration_in_stock() - 1), 0)
        self.assertEqual(self.batch.remaining_stock(constants.START_DATE + self.batch.duration_in_stock()), 0)
