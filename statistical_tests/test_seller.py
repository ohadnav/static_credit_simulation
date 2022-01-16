from common import constants
from common.context import DataGenerator, SimulationContext
from common.util import Dollar, Percent
from finance.underwriting import Underwriting
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
            change_factor = 1.5
            change_factor_price = 3
            is_true.append(
                (
                    data_generator.cogs_margin_median / change_factor < product.cogs_margin < change_factor *
                    data_generator.cogs_margin_median, product))
            is_true.append(
                (
                    data_generator.manufacturing_duration_avg / change_factor < product.manufacturing_duration <
                    change_factor * data_generator.manufacturing_duration_avg,
                    product))
            is_true.append(
                (
                    data_generator.median_price / change_factor_price < product.price < change_factor_price *
                    data_generator.median_price,
                    product))
            is_true.append(
                (
                    constants.MIN_PURCHASE_ORDER_SIZE * 2 < product.min_purchase_order_size <
                    constants.MIN_PURCHASE_ORDER_SIZE * 20,
                    (product.min_purchase_order_size / constants.MIN_PURCHASE_ORDER_SIZE, product)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.4, max_frequency=0.8, times=1000)

    def test_generated_merchant_top_line(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            data_generator.max_num_products = constants.MAX_NUM_PRODUCTS
            factor = 1.5
            data_generator.num_products = constants.NUM_PRODUCTS * factor
            data_generator.num_products_std *= factor
            merchant = Merchant.generate_simulated(data_generator)
            is_true.append(
                (merchant.annual_top_line(constants.START_DATE) > Dollar(10 ** 5),
                (merchant.annual_top_line(constants.START_DATE), merchant)))
            is_true.append(
                (merchant.annual_top_line(constants.START_DATE) < Dollar(10 ** 6),
                (merchant.annual_top_line(constants.START_DATE), merchant)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.6, max_frequency=0.99, times=200)

    def test_generated_merchant(self):
        def test_iteration(data_generator: DataGenerator, *args, **kwargs):
            is_true = []
            data_generator.max_num_products = constants.MAX_NUM_PRODUCTS
            data_generator.num_products = constants.NUM_PRODUCTS
            merchant = Merchant.generate_simulated(data_generator)
            change_factor_small = 1.25
            change_factor_big = 1.5

            is_true.append(
                (0 < merchant.profit_margin(constants.START_DATE) < 0.2, merchant.profit_margin(constants.START_DATE)))
            is_true.append(
                (
                    data_generator.inventory_turnover_ratio_median / change_factor_big <
                    merchant.inventory_turnover_ratio(
                        constants.START_DATE) < change_factor_big * data_generator.inventory_turnover_ratio_median,
                    merchant.inventory_turnover_ratio(constants.START_DATE)))
            is_true.append(
                (
                    data_generator.roas_median / change_factor_small < merchant.roas(constants.START_DATE) < \
                    change_factor_small * data_generator.roas_median, merchant.roas(constants.START_DATE)))
            is_true.append(
                (
                    data_generator.organic_rate_median / change_factor_small < merchant.organic_rate(
                        constants.START_DATE) < change_factor_small * data_generator.organic_rate_median,
                    merchant.organic_rate(constants.START_DATE)))
            is_true.append(
                (
                    data_generator.out_of_stock_rate_median / change_factor_small < merchant.out_of_stock_rate(
                        constants.START_DATE) < \
                    change_factor_small * data_generator.out_of_stock_rate_median,
                    merchant.out_of_stock_rate(constants.START_DATE)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.4, max_frequency=0.85, times=1000)

    def test_generated_merchant_num_products(self):
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
            change_factor_volatile = 1.8
            change_factor_controlled = 1.33
            is_true.append(
                (
                    data_generator.inventory_turnover_ratio_median / change_factor_volatile <
                    batch.inventory_turnover_ratio < \
                    change_factor_volatile * data_generator.inventory_turnover_ratio_median,
                    round(batch.inventory_turnover_ratio, 1), round(constants.YEAR / batch.lead_time, 1),
                    batch.inventory_turnover_ratio == constants.YEAR / batch.lead_time))
            is_true.append(
                (
                    data_generator.roas_median / change_factor_controlled < batch.roas < \
                    change_factor_controlled * data_generator.roas_median, batch.roas))
            is_true.append(
                (
                    data_generator.organic_rate_median / change_factor_controlled < batch.organic_rate < \
                    change_factor_controlled * data_generator.organic_rate_median, round(batch.organic_rate, 2),
                    round(batch.roas, 2), batch.organic_rate == data_generator.organic_rate_median))
            is_true.append(
                (
                    data_generator.out_of_stock_rate_median / change_factor_controlled < batch.out_of_stock_rate < \
                    change_factor_controlled * data_generator.out_of_stock_rate_median, batch.out_of_stock_rate))
            is_true.append(
                (
                    batch.product.min_purchase_order_size * 2 < batch.stock < batch.product.min_purchase_order_size *
                    10,
                    round(batch.stock / batch.product.min_purchase_order_size, 2),
                    round(batch.stock / batch.lead_time, 2), batch))
            is_true.append((0 < batch.profit_margin() < 0.2, round(batch.profit_margin(), 2)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.3, max_frequency=0.7, times=1000)

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

    def test_risk_scores_distribution(self):
        mid_score = Percent(0.5)
        small_margin = 0.1
        big_margin = 0.25
        risk_to_margin = {k: big_margin for k, v in vars(self.context.risk_context).items()}
        risk_to_margin['inventory_turnover_ratio'] = small_margin

        def test_factor(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            merchant = Merchant.generate_simulated(data_generator)
            underwriting = Underwriting(context, merchant)
            score_dict = underwriting.initial_risk_context.score_dict()
            is_true.append(
                (abs(mid_score - underwriting.aggregated_score()) < small_margin,
                ('agg', underwriting.aggregated_score())))
            for k, score in score_dict.items():
                is_true.append((abs(mid_score - score) < risk_to_margin[k], (k, round(score, 2))))

            return is_true

        statistical_test_bool(self, test_factor, min_frequency=0.3, max_frequency=0.8, times=200)
