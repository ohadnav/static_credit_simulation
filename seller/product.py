import math
from typing import Tuple

from autologging import traced, logged

from common import constants
from common.context import DataGenerator
from common.primitives import Primitive
from common.util import Percent, Duration, Stock, Dollar, min_max

CHANGE_THRESHOLD = 1.05


@traced
@logged
class Product(Primitive):
    def __init__(self, data_generator: DataGenerator, price: Dollar, cost_per_unit: Dollar,
                 min_purchase_order_size: Stock, manufacturing_duration: Duration, shipping_duration: Duration,
                 cost_std: Percent, cogs_margin: Percent):
        super(Product, self).__init__(data_generator)
        self.price = price
        self.cost_per_unit = cost_per_unit
        self.min_purchase_order_size = min_purchase_order_size
        self.manufacturing_duration = manufacturing_duration
        self.shipping_duration = shipping_duration
        self.lead_time = self.shipping_duration + self.manufacturing_duration
        self.cost_std = cost_std
        self.cogs_margin = cogs_margin

    @classmethod
    def generate_simulated(cls, data_generator: DataGenerator):
        price = data_generator.median_price * data_generator.normal_ratio(data_generator.price_std)
        cogs_margin = data_generator.cogs_margin_median * data_generator.normal_ratio(
            std=constants.COGS_MARGIN_STD, max_ratio=constants.COGS_MARGIN_MAX / data_generator.cogs_margin_median)
        manufacturing_duration = Duration(
            data_generator.manufacturing_duration_avg * data_generator.normal_ratio(
                data_generator.manufacturing_duration_std))
        shipping_duration = Duration(
            data_generator.shipping_duration_avg * data_generator.normal_ratio(
                data_generator.shipping_duration_std))
        lead_time = manufacturing_duration + shipping_duration
        min_purchase_order_size = Stock(round(constants.MIN_PURCHASE_ORDER_VALUE / (cogs_margin * price)))
        min_purchase_order_size = max([min_purchase_order_size, lead_time, constants.MIN_PURCHASE_ORDER_SIZE])
        new_product = Product(
            data_generator, price, data_generator.cogs_margin_median * price, min_purchase_order_size,
            manufacturing_duration, shipping_duration,
            data_generator.inventory_cost_std, cogs_margin)
        return new_product

    def volume_discount(self, volume: Stock) -> Percent:
        if volume <= self.min_purchase_order_size:
            return 0
        discount_rate = math.log10(volume / self.min_purchase_order_size) * constants.VOLUME_DISCOUNT
        return min_max(discount_rate, 0.0, constants.MAX_VOLUME_DISCOUNT)

    def discounted_cost_per_unit(self, volume: Stock) -> Dollar:
        return self.cost_per_unit * (1 - self.volume_discount(volume))

    def batch_size_from_upfront_cost(self, upfront_cost: Dollar) -> Stock:
        total_cost = upfront_cost * (1 / constants.INVENTORY_UPFRONT_PAYMENT)
        estimated_batch_size = int(total_cost / self.cost_per_unit)
        estimated_discounted_cpu = self.cost_per_unit
        change = 2 * CHANGE_THRESHOLD
        while change > CHANGE_THRESHOLD:
            prev_cpu = estimated_discounted_cpu
            if estimated_batch_size == 0:
                return 0
            estimated_discounted_cpu = self.discounted_cost_per_unit(estimated_batch_size)
            estimated_batch_size = Stock(total_cost / estimated_discounted_cpu)
            change = prev_cpu / estimated_discounted_cpu
        return estimated_batch_size

    def purchase_order_cost(self, purchase_order_size: Stock) -> Tuple[Dollar, Dollar]:
        new_inventory_cost = self.discounted_cost_per_unit(purchase_order_size) * purchase_order_size
        new_inventory_cost *= self.data_generator.normal_ratio(self.cost_std, chance_positive=1)
        upfront_cost = new_inventory_cost * constants.INVENTORY_UPFRONT_PAYMENT
        post_manufacturing_cost = new_inventory_cost - upfront_cost
        return upfront_cost, post_manufacturing_cost