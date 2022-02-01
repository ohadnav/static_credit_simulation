from unittest.mock import MagicMock

from common import constants
from common.local_numbers import Dollar, Duration, Float, Date, ONE
from seller.batch import Batch
from seller.inventory import Inventory
from tests.util_test import BaseTestCase


class TestInventory(BaseTestCase):
    def setUp(self) -> None:
        super(TestInventory, self).setUp()
        self.inventory = Inventory.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        for batch in self.inventory.batches:
            self.assertEqual(batch.product, self.inventory.product)
        for i in range(len(self.inventory.batches) - 1):
            self.assertEqual(self.inventory.batches[i].last_date + 1, self.inventory.batches[i + 1].start_date)
            self.assertEqual(self.inventory.batches[i].sgna_rate, self.inventory.batches[i + 1].sgna_rate)
        self.assertGreater(self.inventory.batches[-1].start_date, self.data_generator.simulated_duration)

    def test_current_batch(self):
        self.assertEqual(self.inventory[self.data_generator.start_date], self.inventory.batches[0])
        self.assertEqual(self.inventory[self.inventory.batches[0].last_date + 1], self.inventory.batches[1])

    def test_gp_per_day(self):
        self.assertEqual(
            self.inventory.gp_per_day(self.data_generator.start_date),
            self.inventory.batches[0].gp_per_day(self.data_generator.start_date))
        self.inventory.batches[0].initiate_new_purchase_order(
            self.inventory.batches[0].get_purchase_order_start_date(), Dollar(10000000))
        next_batch_day = self.inventory.batches[0].last_date + 1
        self.assertEqual(
            self.inventory.gp_per_day(next_batch_day),
            self.inventory.batches[1].gp_per_day(next_batch_day))

    def test_revenue_per_day(self):
        self.assertEqual(
            self.inventory.revenue_per_day(self.data_generator.start_date),
            self.inventory.batches[0].revenue_per_day(self.data_generator.start_date))
        self.inventory.batches[0].initiate_new_purchase_order(
            self.inventory.batches[0].get_purchase_order_start_date(), Dollar(10000000))
        next_batch_day = self.inventory.batches[0].last_date + 1
        self.assertEqual(
            self.inventory.revenue_per_day(next_batch_day),
            self.inventory.batches[1].revenue_per_day(next_batch_day))

    def test_current_inventory_valuation(self):
        batch: Batch = self.inventory[self.data_generator.start_date]
        ten = Float(10)
        five = Float(5)
        batch.remaining_stock = MagicMock(side_effect=[ten, five])
        batch.sales_velocity = MagicMock(return_value=five)
        batch.product.price = 2
        self.assertEqual(
            self.inventory.current_inventory_valuation(self.data_generator.start_date),
            ten + ten * constants.INVENTORY_NPV_DISCOUNT_FACTOR)
        self.assertEqual(self.inventory.current_inventory_valuation(self.data_generator.start_date + 1), ten)
        batch.sales_velocity = MagicMock(return_value=0)
        self.assertEqual(self.inventory.current_inventory_valuation(self.data_generator.start_date), 0)

    def test_purchase_order_valuation(self):
        batch: Batch = self.inventory[self.data_generator.start_date]
        batch.initiate_new_purchase_order(batch.get_purchase_order_start_date(), Dollar(10000000))
        velocity = Float(4)
        batch.purchase_order.stock = velocity * 2
        batch.last_date = Date(2)
        batch.sales_velocity = MagicMock(return_value=velocity)
        batch.product.price = ONE
        dv = batch.product.price * velocity
        r = constants.INVENTORY_NPV_DISCOUNT_FACTOR
        self.assertEqual(
            self.inventory.purchase_order_valuation(self.data_generator.start_date), dv * (r ** 2) + dv * (r ** 3))
        self.assertEqual(
            self.inventory.purchase_order_valuation(self.data_generator.start_date + 1),
            dv * (r ** 1) + dv * (r ** 2))
        batch.sales_velocity = MagicMock(return_value=0)
        self.assertEqual(self.inventory.purchase_order_valuation(self.data_generator.start_date), 0)

    def test_valuation(self):
        day = self.data_generator.start_date
        self.data_generator.include_purchase_order_in_valuation = False
        self.assertEqual(self.inventory.valuation(day), self.inventory.current_inventory_valuation(day))
        self.data_generator.include_purchase_order_in_valuation = True
        self.assertEqual(
            self.inventory.valuation(day), self.inventory.current_inventory_valuation(
                day) + self.inventory.purchase_order_valuation(day))

    def test_num_batches(self):
        self.data_generator.remove_randomness()
        self.data_generator.inventory_turnover_ratio_median = 5
        self.inventory = Inventory.generate_simulated(self.data_generator)
        ratio = self.data_generator.simulated_duration / constants.YEAR
        if ratio < 1:
            ratio = 1 / ratio
        self.assertEqual(
            len(self.inventory.batches),
            self.data_generator.inventory_turnover_ratio_median * ratio + 1)

    def test_discounted_inventory_value(self):
        r = constants.INVENTORY_NPV_DISCOUNT_FACTOR
        self.assertEqual(Inventory.discounted_inventory_value(Dollar(2), Duration(2)), 1 + r)
        self.assertEqual(Inventory.discounted_inventory_value(Dollar(9), Duration(3)), 3 + 3 * r + 3 * r * r)
        self.assertEqual(
            Inventory.discounted_inventory_value(Dollar(9), Duration(3), Duration(1)),
            3 * r + 3 * r * r + 3 * r * r * r)
        self.assertEqual(Inventory.discounted_inventory_value(Dollar(2), Duration(0)), 0)
