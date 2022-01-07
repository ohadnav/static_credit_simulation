import logging
import sys
from typing import List, Union, Tuple, Any
from unittest import TestCase

from common import constants
from common.context import DataGenerator
from seller.batch import Batch
from seller.inventory import Inventory
from seller.merchant import Merchant
from seller.product import Product
from statistical_tests.statistical_test import statistical_test_bool, statistical_test_mean_error


class TestStatisticalSeller(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=logging.WARNING, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()

    @statistical_test_bool(num_lists=4)
    def test_generated_product(self, is_true: List[List[Union[bool, Tuple[bool, Any]]]]):
        self.product = Product.generate_simulated(self.data_generator)
        is_true[0].append(
            self.data_generator.cogs_margin_median / 1.5 < self.product.cogs_margin < 1.5 *
            self.data_generator.cogs_margin_median)
        is_true[1].append(1.5 * constants.WEEK < self.product.manufacturing_duration < 2 * constants.MONTH)
        is_true[2].append(
            self.data_generator.median_price / 4 < self.product.price < 4 * self.data_generator.median_price)
        is_true[3].append(
            constants.MIN_PURCHASE_ORDER_SIZE * 2 < self.product.min_purchase_order_size <
            constants.MIN_PURCHASE_ORDER_SIZE * 200)

    @statistical_test_bool(num_lists=2)
    def test_generated_merchant(self, is_true: List[List[Union[bool, Tuple[bool, Any]]]]):
        self.data_generator.max_num_products = constants.MAX_NUM_PRODUCTS
        self.data_generator.num_products = constants.NUM_PRODUCTS
        self.merchant = Merchant.generate_simulated(self.data_generator)
        is_true[0].append(
            self.data_generator.num_products / 2 <= len(
                self.merchant.inventories) <= self.data_generator.num_products * 4)
        is_true[1].append((self.merchant.suspension_start_date is None, self.merchant.suspension_start_date))

    @statistical_test_bool(num_lists=7)
    def test_generated_batches(self, is_true: List[List[Tuple[bool, Any]]]):
        self.batch = Batch.generate_simulated(self.data_generator)
        is_true[0].append(
            (
                self.data_generator.shipping_duration_avg / 2 < self.batch.shipping_duration < 2 *
                self.data_generator.shipping_duration_avg,
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
                self.batch.lead_time * 3 < self.batch.stock < constants.MIN_PURCHASE_ORDER_SIZE * 5000,
                self.batch.stock))
        is_true[6].append((-0.15 < self.batch.profit_margin() < 0.2, round(self.batch.profit_margin(), 2)))

    @statistical_test_mean_error
    def test_out_of_stock_statistical_test(self, errors):
        count_oos = 0
        self.batch = Batch.generate_simulated(self.data_generator)
        for day in range(self.batch.start_date, self.batch.last_date + 1):
            if self.batch.is_out_of_stock(day):
                count_oos += 1
        oos_error = abs(count_oos / self.batch.duration - self.batch.out_of_stock_rate)
        errors.append(oos_error)

    @statistical_test_bool(num_lists=3)
    def test_random_distribution(self, is_true: List[List[Tuple[bool, Any]]]):
        value1 = self.data_generator.normal_ratio()
        value2 = self.data_generator.normal_ratio(chance_positive=0.8)
        value3 = self.data_generator.normal_ratio(chance_positive=0.2)
        is_true[0].append((0.5 < value1 < 2, value1))
        is_true[1].append((0.7 < value2 < 2, value2))
        is_true[2].append((0.5 < value3 < 1.5, value3))

    @statistical_test_mean_error(times=10)
    def test_annual_top_line(self, errors: List[float]):
        self.inventory: Inventory = Inventory.generate_simulated(self.data_generator)
        expected_sales = self.inventory[
                             constants.START_DATE].sales_velocity() * constants.YEAR * self.inventory.product.price * (
                                 1 - self.inventory[constants.START_DATE].out_of_stock_rate)
        actual_top_line = self.inventory.annual_top_line(constants.START_DATE)
        diff = abs(actual_top_line / expected_sales - 1)
        errors.append(diff)
