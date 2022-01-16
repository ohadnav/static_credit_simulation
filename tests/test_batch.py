from random import randint
from unittest.mock import MagicMock

from common.numbers import Percent, Dollar, O, ONE, Date, Duration
from seller.batch import Batch, PurchaseOrder
from tests.util_test import BaseTestCase


class TestBatch(BaseTestCase):
    def setUp(self) -> None:
        super(TestBatch, self).setUp()
        self.batch: Batch = Batch.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        ratio = 1.1
        self.data_generator.normal_ratio = MagicMock(return_value=ratio)
        self.batch = Batch.generate_simulated(self.data_generator)
        self.assertAlmostEqual(
            self.batch.sgna_rate, self.data_generator.sgna_rate * ratio)
        self.assertAlmostEqual(
            self.batch.inventory_turnover_ratio, self.data_generator.inventory_turnover_ratio_median * ratio)
        self.assertAlmostEqual(self.batch.out_of_stock_rate, self.data_generator.out_of_stock_rate_median * ratio)
        self.assertAlmostEqual(self.batch.roas, self.data_generator.roas_median * ratio)
        self.assertAlmostEqual(self.batch.organic_rate, self.data_generator.organic_rate_median * ratio)
        self.assertEqual(self.batch.shipping_duration, int(self.data_generator.shipping_duration_avg * ratio))
        self.assertEqual(
            self.batch.stock,
            int(max(self.batch.lead_time + 1, self.batch.product.min_purchase_order_size) * ratio))
        self.assertEqual(self.batch.start_date, self.data_generator.start_date)
        self.assertIsNone(self.batch.next_batch)

    def test_generate_simulated_with_previous(self):
        ratio = 1.1
        sgna_rate = Percent(0.2)
        self.data_generator.normal_ratio = MagicMock(return_value=ratio)
        self.batch = Batch.generate_simulated(self.data_generator, sgna_rate=sgna_rate)
        batch2 = Batch.generate_simulated(self.data_generator, previous=self.batch)
        self.assertEqual(self.batch.product, batch2.product)
        self.assertAlmostEqual(
            batch2.inventory_turnover_ratio, self.batch.inventory_turnover_ratio * ratio)
        self.assertAlmostEqual(batch2.out_of_stock_rate, self.batch.out_of_stock_rate * ratio)
        self.assertAlmostEqual(batch2.roas, self.batch.roas * ratio)
        self.assertAlmostEqual(batch2.organic_rate, self.batch.organic_rate * ratio)
        self.assertAlmostEqual(batch2.sgna_rate, self.batch.sgna_rate)
        self.assertEqual(batch2.stock, 0)
        self.assertEqual(batch2.start_date, self.batch.last_date + 1)

    def test_has_future_revenue(self):
        self.batch.is_out_of_stock = MagicMock(return_value=True)
        self.batch.stock = 0
        self.batch.purchase_order = None
        duration = Duration(randint(self.batch.start_date, self.batch.last_date))
        self.assertFalse(self.batch.has_future_revenue(duration))
        self.batch.purchase_order = PurchaseOrder(Date(1), ONE, ONE)
        self.assertTrue(self.batch.has_future_revenue(duration))
        self.batch.purchase_order = None
        self.batch.stock = 1
        self.assertFalse(self.batch.has_future_revenue(duration))
        self.batch.is_out_of_stock = MagicMock(return_value=False)
        self.assertTrue(self.batch.has_future_revenue(duration))
        self.batch.stock = 0
        self.assertFalse(self.batch.has_future_revenue(duration))

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
        self.batch.purchase_order = PurchaseOrder(Date(0), O, O)
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

        self.batch.product.purchase_order_cost = MagicMock(
            side_effect=[(self.data_generator.max_purchase_order_value, self.data_generator.max_purchase_order_value),
                (ONE, ONE)])
        stock = self.batch.product.batch_size_from_cost(self.data_generator.max_purchase_order_value)
        self.assertEqual(self.batch.max_purchase_order(), PurchaseOrder(stock, ONE, ONE))

    def test_initiate_new_purchase_order(self):
        self.data_generator.remove_randomness()
        self.data_generator.conservative_cash_management = False
        batch2 = Batch.generate_simulated(self.data_generator, previous=self.batch)
        upfront, post = self.batch.product.purchase_order_cost(self.batch.product.min_purchase_order_size)
        self.assertIsNone(self.batch.initiate_new_purchase_order(self.batch.get_purchase_order_start_date(), post - 1))
        self.assertIsNotNone(self.batch.initiate_new_purchase_order(self.batch.get_purchase_order_start_date(), post))
        self.assertEqual(
            self.batch.purchase_order, PurchaseOrder(self.batch.product.min_purchase_order_size, upfront, post))
        self.assertEqual(batch2.stock, self.batch.product.min_purchase_order_size)
        upfront2, post2 = self.batch.product.purchase_order_cost(self.batch.max_stock_for_next_purchase_order())
        self.batch.extend_duration = MagicMock()
        self.assertIsNotNone(
            self.batch.initiate_new_purchase_order(self.batch.get_purchase_order_start_date() + 2, post2))
        self.assertEqual(
            self.batch.purchase_order, PurchaseOrder(self.batch.max_stock_for_next_purchase_order(), upfront2, post2))
        self.assertEqual(self.batch.purchase_order.stock, batch2.stock)
        self.batch.extend_duration.assert_called()

    def test_push_start_date(self):
        batch2: Batch = Batch.generate_simulated(self.data_generator)
        prev_start1 = self.batch.start_date
        prev_start2 = batch2.start_date
        prev_end1 = self.batch.last_date
        prev_end2 = batch2.last_date
        extension = Duration(2)
        self.batch.push_start_date(extension)
        self.assertEqual(self.batch.start_date, prev_start1 + extension)
        self.assertEqual(self.batch.last_date, prev_end1 + extension)
        self.assertEqual(batch2.start_date, prev_start2)
        self.assertEqual(batch2.last_date, prev_end2)
        self.batch.next_batch = batch2
        self.batch.push_start_date(extension)
        self.assertEqual(self.batch.start_date, prev_start1 + 2 * extension)
        self.assertEqual(self.batch.last_date, prev_end1 + 2 * extension)
        self.assertEqual(batch2.start_date, prev_start2 + extension)
        self.assertEqual(batch2.last_date, prev_end2 + extension)

    def test_extend_duration(self):
        self.batch.push_start_date = MagicMock()
        extension = 2
        prev_duration = self.batch.duration
        prev_last = self.batch.last_date
        self.batch.extend_duration(self.batch.get_purchase_order_start_date() + extension)
        self.batch.push_start_date.assert_not_called()
        self.assertEqual(self.batch.duration, prev_duration + extension)
        self.assertEqual(self.batch.last_date, prev_last + extension)
        self.assertFalse(
            self.batch.is_out_of_stock(self.data_generator.start_date + self.batch.duration_in_stock() - 1))
        self.assertTrue(self.batch.is_out_of_stock(self.data_generator.start_date + self.batch.duration_in_stock()))
        batch2 = Batch.generate_simulated(self.data_generator, previous=self.batch)
        batch2.push_start_date = MagicMock()
        self.batch.extend_duration(self.batch.get_purchase_order_start_date() + extension)
        batch2.push_start_date.assert_called()
        self.batch.push_start_date.assert_not_called()

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
        self.data_generator.conservative_cash_management = True
        self.assertEqual(
            self.batch.max_cash_needed(self.batch.get_purchase_order_start_date()),
            self.batch.max_purchase_order().total_cost())
        self.data_generator.conservative_cash_management = False
        self.assertEqual(self.batch.max_cash_needed(self.data_generator.start_date - 1), 0)
        self.assertEqual(
            self.batch.max_cash_needed(self.batch.get_purchase_order_start_date()),
            self.batch.max_purchase_order().post_manufacturing_cost)
        self.assertEqual(
            self.batch.max_cash_needed(self.batch.get_purchase_order_start_date()),
            self.batch.max_purchase_order().post_manufacturing_cost)
        upfront, post = self.batch.product.purchase_order_cost(self.batch.product.min_purchase_order_size)
        self.assertIsNotNone(self.batch.initiate_new_purchase_order(self.batch.get_purchase_order_start_date(), post))
        self.assertEqual(self.batch.max_cash_needed(self.batch.get_manufacturing_done_date()), post)

    def test_cash_needed_to_afford_purchase_order(self):
        self.data_generator.conservative_cash_management = True
        purchase_order = PurchaseOrder(Date(1), Dollar(2), Dollar(3))
        self.assertEqual(self.batch.cash_needed_to_afford_purchase_order(purchase_order), Dollar(5))
        self.data_generator.conservative_cash_management = False
        self.assertEqual(self.batch.cash_needed_to_afford_purchase_order(purchase_order), Dollar(3))

    def test_inventory_cost(self):
        self.data_generator.remove_randomness()
        self.data_generator.conservative_cash_management = False
        upfront, post = self.batch.product.purchase_order_cost(self.batch.product.min_purchase_order_size)
        million = Dollar(1000000)
        if self.batch.get_purchase_order_start_date() > self.data_generator.start_date:
            self.assertEqual(self.batch.inventory_cost(self.batch.get_purchase_order_start_date() - 1, million), 0)
        self.assertIsNone(self.batch.purchase_order)
        self.assertEqual(self.batch.inventory_cost(self.batch.get_purchase_order_start_date(), post - 1), 0)
        self.assertIsNone(self.batch.purchase_order)
        self.assertAlmostEqual(self.batch.inventory_cost(self.batch.get_purchase_order_start_date(), post), upfront)
        self.assertEqual(
            self.batch.purchase_order, PurchaseOrder(self.batch.product.min_purchase_order_size, upfront, post))
        self.assertAlmostEqual(self.batch.inventory_cost(self.batch.get_manufacturing_done_date(), O), post)
        self.assertAlmostEqual(self.batch.inventory_cost(self.batch.get_manufacturing_done_date() + 1, million), 0)

    def test_is_out_of_stock(self):
        self.assertFalse(self.batch.is_out_of_stock(self.data_generator.start_date))
        self.assertFalse(
            self.batch.is_out_of_stock(self.data_generator.start_date + self.batch.duration_in_stock() - 1))
        self.assertTrue(self.batch.is_out_of_stock(self.data_generator.start_date + self.batch.duration_in_stock()))

    def test_sales_velocity(self):
        self.batch.stock = 30
        self.batch.duration = 4
        self.batch.out_of_stock_rate = 0.25
        self.assertAlmostEqual(self.batch.sales_velocity(), 10)

    def test_revenue_per_day(self):
        self.assertEqual(
            self.batch.revenue_per_day(self.data_generator.start_date + self.batch.duration_in_stock() + 1), 0)
        self.batch.revenue_margin = MagicMock(return_value=1)
        self.assertAlmostEqual(
            self.batch.revenue_per_day(self.data_generator.start_date),
            self.batch.product.price * self.batch.sales_velocity())

    def test_revenue_margin(self):
        self.assertGreater(self.batch.revenue_margin(), 0)

    def test_gp_per_day(self):
        self.assertEqual(self.batch.gp_per_day(self.data_generator.start_date + self.batch.duration_in_stock() + 1), 0)
        self.batch.gp_margin = MagicMock(return_value=0.8)
        self.assertAlmostEqual(
            self.batch.total_revenue_per_day(self.data_generator.start_date) * 0.8,
            self.batch.gp_per_day(self.data_generator.start_date))

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
        self.assertEqual(self.batch.remaining_stock(self.data_generator.start_date), self.batch.stock)
        self.assertEqual(
            self.batch.remaining_stock(self.data_generator.start_date + 1),
            self.batch.stock - int(self.batch.sales_velocity()))
        self.assertGreater(
            self.batch.remaining_stock(self.data_generator.start_date + self.batch.duration_in_stock() - 1), 0)
        self.assertEqual(self.batch.remaining_stock(self.data_generator.start_date + self.batch.duration_in_stock()), 0)
