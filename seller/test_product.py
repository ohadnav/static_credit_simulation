import logging
import sys
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE, traced, logged

from common import constants
from common.context import DataGenerator
from common.util import Dollar
from seller.product import Product


@traced
@logged
class TestProduct(TestCase):
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
        self.product = Product.generate_simulated(self.data_generator)

    def test_generate_simulated(self):
        ratio = 0.9
        self.data_generator.normal_ratio = MagicMock(return_value=ratio)
        self.product = Product.generate_simulated(self.data_generator)
        self.assertAlmostEqual(self.product.price, self.data_generator.median_price * ratio)
        self.assertAlmostEqual(self.product.cogs_margin, self.data_generator.cogs_margin_median * ratio)
        self.assertEqual(
            self.product.manufacturing_duration, int(self.data_generator.manufacturing_duration_avg * ratio))
        self.assertEqual(self.product.shipping_duration, int(self.data_generator.shipping_duration_avg * ratio))
        self.assertGreater(
            self.product.min_purchase_order_size, max(self.product.lead_time, constants.MIN_PURCHASE_ORDER_SIZE))

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

    def test_batch_size_from_upfront_cost(self):
        self.data_generator.remove_randomness()
        self.assertAlmostEqual(
            self.product.batch_size_from_upfront_cost(
                self.product.purchase_order_cost(self.product.min_purchase_order_size)[0]),
            self.product.min_purchase_order_size)
        self.assertGreater(
            self.product.batch_size_from_upfront_cost(
                self.product.purchase_order_cost(self.product.min_purchase_order_size * 11)[0]),
            self.product.min_purchase_order_size * 10)

    def test_purchase_order_cost(self):
        self.data_generator.remove_randomness()
        total_cost: Dollar = self.product.min_purchase_order_size * self.product.cost_per_unit
        # noinspection PyTypeChecker
        self.assertAlmostEqual(
            self.product.purchase_order_cost(self.product.min_purchase_order_size), (
                total_cost * constants.INVENTORY_UPFRONT_PAYMENT,
                total_cost * (1 - constants.INVENTORY_UPFRONT_PAYMENT)))
        self.assertLess(
            self.product.purchase_order_cost(10 * self.product.min_purchase_order_size), (
                10 * self.product.min_purchase_order_size * self.product.cost_per_unit * constants.INVENTORY_UPFRONT_PAYMENT,
                10 * self.product.min_purchase_order_size * self.product.cost_per_unit * (
                        1 - constants.INVENTORY_UPFRONT_PAYMENT)))