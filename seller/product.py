from __future__ import annotations

import math
from typing import Tuple

from common import constants
from common.context import DataGenerator
from common.local_numbers import Percent, Duration, Stock, Dollar, O, O_INT
from common.primitive import Primitive
from common.util import min_max

CHANGE_THRESHOLD = 1.02


class Product(Primitive):
    def __init__(
            self, data_generator: DataGenerator, price: Dollar, min_purchase_order_size: Stock,
            manufacturing_duration: Duration, cogs_margin: Percent):
        super(Product, self).__init__(data_generator)
        self.price = price
        self.cost_per_unit = price * cogs_margin
        self.min_purchase_order_size = min_purchase_order_size
        self.manufacturing_duration = manufacturing_duration
        self.cogs_margin = cogs_margin

    @classmethod
    def generate_simulated(cls, data_generator: DataGenerator) -> Product:
        price = data_generator.median_price * data_generator.normal_ratio(
            data_generator.price_std * data_generator.first_batch_std_factor)
        cogs_margin = cls.generate_cogs_margin(data_generator)
        manufacturing_duration = cls.generate_manufacturing_duration(data_generator)
        cost_per_unit = cogs_margin * price
        min_purchase_order_size = Stock(round(data_generator.min_purchase_order_value / cost_per_unit))
        new_product = Product(data_generator, price, min_purchase_order_size, manufacturing_duration, cogs_margin)
        return new_product

    @classmethod
    def generate_manufacturing_duration(cls, data_generator):
        manufacturing_duration = Duration(
            data_generator.manufacturing_duration_avg * data_generator.normal_ratio(
                data_generator.manufacturing_duration_std * data_generator.first_batch_std_factor))
        manufacturing_duration = min_max(
            manufacturing_duration, constants.MANUFACTURING_DURATION_MIN, constants.MANUFACTURING_DURATION_MAX)
        return manufacturing_duration

    @classmethod
    def generate_cogs_margin(cls, data_generator):
        cogs_margin = data_generator.cogs_margin_median * data_generator.normal_ratio(
            data_generator.cogs_margin_std * data_generator.first_batch_std_factor,
            chance_positive=data_generator.chance_first_batch_better)
        cogs_margin = min_max(cogs_margin, constants.COGS_MARGIN_MIN, constants.COGS_MARGIN_MAX)
        return cogs_margin

    def volume_discount(self, volume: Stock) -> Percent:
        if volume <= self.min_purchase_order_size:
            return O
        discount_rate = math.log10(volume / self.min_purchase_order_size) * constants.VOLUME_DISCOUNT
        return min_max(discount_rate, O, constants.MAX_VOLUME_DISCOUNT)

    def discounted_cost_per_unit(self, volume: Stock) -> Dollar:
        return self.cost_per_unit * (1 - self.volume_discount(volume))

    def batch_size_from_cost(self, cost: Dollar) -> Stock:
        if self.data_generator.conservative_cash_management:
            total_cost = cost
        else:
            total_cost = cost * (1 / (1 - constants.INVENTORY_UPFRONT_PAYMENT))
        estimated_batch_size = (total_cost / self.cost_per_unit).floor()
        estimated_discounted_cpu = self.cost_per_unit
        change = 2 * CHANGE_THRESHOLD
        while change > CHANGE_THRESHOLD:
            prev_cpu = estimated_discounted_cpu
            if estimated_batch_size == 0:
                return O_INT
            estimated_discounted_cpu = self.discounted_cost_per_unit(estimated_batch_size)
            estimated_batch_size = Stock(total_cost / estimated_discounted_cpu)
            change = prev_cpu / estimated_discounted_cpu
        return estimated_batch_size

    def purchase_order_cost(self, purchase_order_size: Stock) -> Tuple[Dollar, Dollar]:
        new_inventory_cost = self.discounted_cost_per_unit(purchase_order_size) * purchase_order_size
        upfront_cost = new_inventory_cost * constants.INVENTORY_UPFRONT_PAYMENT
        post_manufacturing_cost = new_inventory_cost - upfront_cost
        return upfront_cost, post_manufacturing_cost
