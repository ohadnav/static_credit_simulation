from common import constants
from common.context import DataGenerator
from common.util import Dollar
from seller.batch import Batch
from seller.inventory import Inventory
from seller.merchant import Merchant
from seller.product import Product
from statistical_tests.statistical_test import statistical_test_bool, statistical_test_mean_error
from tests.util_test import StatisticalTestCase


class TestStatisticalSeller(StatisticalTestCase):
    def test_generated_product(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            product = Product.generate_simulated(data_generator)
            is_true = []
            is_true.append(
                (
                    data_generator.cogs_margin_median / 1.5 < product.cogs_margin < 1.5 *
                    data_generator.cogs_margin_median, product))
            is_true.append((1.5 * constants.WEEK < product.manufacturing_duration < 2 * constants.MONTH, product))
            is_true.append(
                (
                    data_generator.median_price / 4 < product.price < 4 * data_generator.median_price, product))
            is_true.append(
                (
                    constants.MIN_PURCHASE_ORDER_SIZE * 2 < product.min_purchase_order_size <
                    constants.MIN_PURCHASE_ORDER_SIZE * 200, (product.min_purchase_order_size, product)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8)

    def test_generated_merchant_top_line(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            data_generator.max_num_products = constants.MAX_NUM_PRODUCTS
            data_generator.num_products = constants.NUM_PRODUCTS
            merchant = Merchant.generate_simulated(data_generator)
            is_true.append(
                (merchant.annual_top_line(constants.START_DATE) > Dollar(100000),
                (merchant.annual_top_line(constants.START_DATE), merchant)))
            is_true.append(
                (merchant.annual_top_line(constants.START_DATE) < Dollar(1000000),
                (merchant.annual_top_line(constants.START_DATE), merchant)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8, max_frequency=0.95)

    def test_generated_merchant_profitability(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            data_generator.max_num_products = constants.MAX_NUM_PRODUCTS
            data_generator.num_products = constants.NUM_PRODUCTS
            merchant = Merchant.generate_simulated(data_generator)
            is_true.append(
                (0 < merchant.profit_margin(constants.START_DATE) < 0.15, merchant.profit_margin(constants.START_DATE)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.4, max_frequency=0.8)

    def test_generated_merchant(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            data_generator.max_num_products = constants.MAX_NUM_PRODUCTS
            data_generator.num_products = constants.NUM_PRODUCTS
            merchant = Merchant.generate_simulated(data_generator)
            is_true.append(
                (
                    data_generator.num_products / 2 <= len(
                        merchant.inventories) <= data_generator.num_products * 4, len(merchant.inventories)))
            is_true.append((merchant.suspension_start_date is None, merchant.suspension_start_date))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8)

    def test_generated_batches(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            batch = Batch.generate_simulated(data_generator)
            is_true.append(
                (
                    data_generator.shipping_duration_avg / 2 < batch.shipping_duration < 2 *
                    data_generator.shipping_duration_avg,
                    batch.shipping_duration))
            is_true.append((constants.MONTH < batch.lead_time < 3 * constants.MONTH, batch.lead_time))
            is_true.append(
                (
                    data_generator.inventory_turnover_ratio_median / 2 < batch.inventory_turnover_ratio < \
                    2 * data_generator.inventory_turnover_ratio_median, batch.inventory_turnover_ratio))
            is_true.append(
                (
                    data_generator.roas_median / 1.5 < batch.roas < \
                    1.5 * data_generator.roas_median, batch.roas))
            is_true.append(
                (
                    data_generator.organic_rate_median / 2 < batch.organic_rate < \
                    2 * data_generator.organic_rate_median, batch.organic_rate))
            is_true.append(
                (
                    batch.lead_time * 3 < batch.stock < constants.MIN_PURCHASE_ORDER_SIZE * 5000,
                    batch.stock))
            is_true.append((-0.15 < batch.profit_margin() < 0.2, round(batch.profit_margin(), 2)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8)

    def test_out_of_stock_statistical_test(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            count_oos = 0
            batch = Batch.generate_simulated(data_generator)
            for day in range(batch.start_date, batch.last_date + 1):
                if batch.is_out_of_stock(day):
                    count_oos += 1
            oos_error = abs(count_oos / batch.duration - batch.out_of_stock_rate)
            return oos_error

        statistical_test_mean_error(self, test_iteration)

    def test_random_distribution(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            value1 = data_generator.normal_ratio()
            value2 = data_generator.normal_ratio(chance_positive=0.8)
            value3 = data_generator.normal_ratio(chance_positive=0.2)
            is_true.append((0.5 < value1 < 2, value1))
            is_true.append((0.7 < value2 < 2, value2))
            is_true.append((0.5 < value3 < 1.5, value3))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8)

    def test_annual_top_line(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            inventory = Inventory.generate_simulated(data_generator)
            expected_sales = inventory[
                                 constants.START_DATE].sales_velocity() * constants.YEAR * inventory.product.price * (
                                     1 - inventory[constants.START_DATE].out_of_stock_rate)
            actual_top_line = inventory.annual_top_line(constants.START_DATE)
            diff = abs(actual_top_line / expected_sales - 1)
            return diff

        statistical_test_mean_error(self, test_iteration)
