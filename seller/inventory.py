import math
from typing import Optional, List

from autologging import logged, traced

from common import constants
from common.context import DataGenerator
from common.primitives import Primitive
from common.util import Date, Dollar, Duration
from seller.batch import Batch
from seller.product import Product


@traced
@logged
class Inventory(Primitive):
    def __init__(self, data_generator: DataGenerator, product: Product, batches: List[Batch]):
        super(Inventory, self).__init__(data_generator)
        self.product = product
        self.batches = batches

    @classmethod
    def generate_simulated(cls, data_generator: DataGenerator,
                           product: Optional[Product] = None):
        product = product or Product.generate_simulated(data_generator)
        batches = [Batch.generate_simulated(data_generator, product)]
        total_duration = batches[0].duration
        while total_duration < constants.SIMULATION_DURATION:
            next_batch = Batch.generate_simulated(data_generator, previous=batches[-1])
            total_duration += next_batch.duration
            batches.append(next_batch)
        new_inventory = Inventory(data_generator, product, batches)
        return new_inventory

    def __getitem__(self, day) -> Batch:
        return [batch for batch in self.batches if batch.start_date <= day <= batch.last_date][0]

    def annual_top_line(self, day: Date) -> Dollar:
        return self[day].inventory_turnover_ratio * self[day].stock * self.product.price

    def gp_per_day(self, day: Date) -> Dollar:
        return self[day].gp_per_day(day)

    def revenue_per_day(self, day: Date) -> Dollar:
        return self[day].revenue_per_day(day)

    def purchase_order_valuation(self, day: Date) -> Dollar:
        if not self[day].purchase_order:
            return 0
        purchase_order_stock = self[day].purchase_order.stock
        next_purchase_order_value = purchase_order_stock * self.product.price
        remaining_lead_time = self[day].last_date - day + 1
        time_to_sell = math.ceil(purchase_order_stock / self[day].sales_velocity())
        return Inventory.discounted_inventory_value(next_purchase_order_value, time_to_sell, remaining_lead_time)

    def current_inventory_valuation(self, day: Date):
        remaining_stock = self[day].remaining_stock(day)
        stock_value = remaining_stock * self.product.price
        time_to_sell = math.ceil(remaining_stock / self[day].sales_velocity())
        return Inventory.discounted_inventory_value(stock_value, time_to_sell)

    def valuation(self, day: Date) -> Dollar:
        current_value = self.current_inventory_valuation(day)
        next_po_value = self.purchase_order_valuation(day)
        if self.data_generator.include_purchase_order_in_valuation:
            return current_value + next_po_value
        return current_value

    @staticmethod
    def discounted_inventory_value(stock_value: Dollar, duration_to_sell: Duration,
                                   remaining_lead_time: Duration = 0) -> Dollar:
        value_per_day = stock_value / duration_to_sell
        daily_value_discount = constants.INVENTORY_NPV_DISCOUNT_FACTOR
        lead_time_factor = math.pow(daily_value_discount, remaining_lead_time)
        geometric_series_sum_factor = (1 - math.pow(daily_value_discount, duration_to_sell)) / (
                    1 - daily_value_discount)
        return value_per_day * geometric_series_sum_factor * lead_time_factor
