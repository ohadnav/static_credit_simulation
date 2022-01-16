from unittest.mock import MagicMock

from common import constants
from common.numbers import Dollar
from seller.product import Product
from tests.util_test import BaseTestCase


class TestProduct(BaseTestCase):
    def setUp(self) -> None:
        super(TestProduct, self).setUp()
        self.product = Product.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        ratio = 0.9
        self.data_generator.normal_ratio = MagicMock(return_value=ratio)
        self.product = Product.generate_simulated(self.data_generator)
        self.assertAlmostEqual(self.product.price, self.data_generator.median_price * ratio)
        self.assertAlmostEqual(self.product.cost_per_unit, self.product.cogs_margin * self.product.price)
        self.assertAlmostEqual(self.product.cogs_margin, self.data_generator.cogs_margin_median * ratio)
        self.assertEqual(
            self.product.manufacturing_duration, int(self.data_generator.manufacturing_duration_avg * ratio))
        self.assertGreater(
            self.product.min_purchase_order_size, constants.MIN_PURCHASE_ORDER_SIZE)

    def test__discount(self):
        self.assertEqual(self.product.volume_discount(self.product.min_purchase_order_size), 0)
        self.assertAlmostEqual(
            self.product.volume_discount(self.product.min_purchase_order_size * 10), constants.VOLUME_DISCOUNT)
        self.assertAlmostEqual(
            self.product.volume_discount(self.product.min_purchase_order_size * 100000000000),
            constants.MAX_VOLUME_DISCOUNT)

    def test_discounted_cost_per_unit(self):
        self.assertEqual(
            self.product.discounted_cost_per_unit(self.product.min_purchase_order_size), self.product.cost_per_unit)
        self.assertAlmostEqual(
            self.product.discounted_cost_per_unit(10 * self.product.min_purchase_order_size),
            self.product.cost_per_unit * (1 - constants.VOLUME_DISCOUNT))

    def test_batch_size_from_cost(self):
        self.data_generator.remove_randomness()
        self.data_generator.conservative_cash_management = False
        self.assertEqual(
            self.product.batch_size_from_cost(
                self.product.purchase_order_cost(self.product.min_purchase_order_size)[1]),
            self.product.min_purchase_order_size)
        self.assertGreater(
            self.product.batch_size_from_cost(
                self.product.purchase_order_cost(self.product.min_purchase_order_size * 11)[1]),
            self.product.min_purchase_order_size * 10)
        self.data_generator.conservative_cash_management = True
        upfront, post = self.product.purchase_order_cost(self.product.min_purchase_order_size)
        total_cost = upfront + post
        self.assertEqual(self.product.min_purchase_order_size, self.product.batch_size_from_cost(total_cost))
        self.assertLess(self.product.batch_size_from_cost(total_cost - 1), self.product.min_purchase_order_size)

    def test_purchase_order_cost(self):
        self.data_generator.remove_randomness()
        total_cost: Dollar = self.product.min_purchase_order_size * self.product.cost_per_unit
        upfront, post = self.product.purchase_order_cost(self.product.min_purchase_order_size)
        # noinspection PyTypeChecker
        self.assertAlmostEqual(upfront, total_cost * constants.INVENTORY_UPFRONT_PAYMENT)
        self.assertAlmostEqual(post, total_cost * (1 - constants.INVENTORY_UPFRONT_PAYMENT))
        self.assertLess(
            self.product.purchase_order_cost(10 * self.product.min_purchase_order_size), (
                10 * self.product.min_purchase_order_size * self.product.cost_per_unit *
                constants.INVENTORY_UPFRONT_PAYMENT,
                10 * self.product.min_purchase_order_size * self.product.cost_per_unit * (
                        1 - constants.INVENTORY_UPFRONT_PAYMENT)))
