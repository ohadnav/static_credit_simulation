from __future__ import annotations

import math
from typing import Optional, List

from common import constants
from common.context import DataGenerator
from common.local_numbers import Percent, Date, Duration, Dollar, O, ONE, Stock
from common.primitive import Primitive
from seller.batch import Batch
from seller.product import Product


class Inventory(Primitive):
    def __init__(self, data_generator: DataGenerator, product: Product, batches: List[Batch]):
        super(Inventory, self).__init__(data_generator)
        self.product = product
        self.batches = batches

    @classmethod
    def generate_simulated(
            cls, data_generator: DataGenerator, sgna_rate: Optional[Percent] = None,
            product: Optional[Product] = None) -> Inventory:
        product = product or Product.generate_simulated(data_generator)
        batches = [Batch.generate_simulated(data_generator, product, sgna_rate)]
        start_date = batches[0].start_date
        while start_date <= data_generator.simulated_duration:
            next_batch = Batch.generate_simulated(data_generator, previous=batches[-1])
            start_date = next_batch.start_date
            batches.append(next_batch)
        new_inventory = Inventory(data_generator, product, batches)
        return new_inventory

    def __getitem__(self, day: Date) -> Batch:
        assert day in self, f'{day} not in {[(batch.start_date, batch.last_date) for batch in self.batches]}'
        return [batch for batch in self.batches if batch.start_date <= day <= batch.last_date][0]

    def __contains__(self, day):
        assert isinstance(day, int)
        return len([batch for batch in self.batches if batch.start_date <= day <= batch.last_date]) > 0

    def annual_top_line(self, day: Date) -> Dollar:
        return self[day].inventory_turnover_ratio * self[day].stock * self.product.price * self[day].revenue_margin()

    def gp_per_day(self, day: Date) -> Dollar:
        return self[day].gp_per_day(day)

    def revenue_per_day(self, day: Date) -> Dollar:
        return self[day].revenue_per_day(day)

    def purchase_order_valuation(self, day: Date) -> Dollar:
        if not self[day].purchase_order:
            return O
        if self[day].sales_velocity() == O:
            return O
        purchase_order_stock = self[day].purchase_order.stock
        next_purchase_order_value = purchase_order_stock * self.product.price
        remaining_lead_time = self[day].last_date.from_date(day)
        time_to_sell = self.duration_to_sell(day, purchase_order_stock)
        return Inventory.discounted_inventory_value(next_purchase_order_value, time_to_sell, remaining_lead_time)

    def current_inventory_valuation(self, day: Date) -> Dollar:
        if self[day].sales_velocity() == 0:
            return O
        remaining_stock = self[day].remaining_stock(day)
        stock_value = remaining_stock * self.product.price
        time_to_sell = self.duration_to_sell(day, remaining_stock)
        return Inventory.discounted_inventory_value(stock_value, time_to_sell)

    def duration_to_sell(self, day: Date, remaining_stock: Stock) -> Duration:
        return Duration(math.ceil(remaining_stock / self[day].sales_velocity()))

    def valuation(self, day: Date) -> Dollar:
        current_value = self.current_inventory_valuation(day)
        if self.data_generator.include_purchase_order_in_valuation:
            next_po_value = self.purchase_order_valuation(day)
            return current_value + next_po_value
        return current_value

    @staticmethod
    def discounted_inventory_value(
            stock_value: Dollar, duration_to_sell: Duration, remaining_lead_time: Duration = Duration(0)) -> Dollar:
        if duration_to_sell == 0:
            return O
        value_per_day = stock_value / duration_to_sell
        daily_value_discount = constants.INVENTORY_NPV_DISCOUNT_FACTOR
        lead_time_factor = daily_value_discount ** remaining_lead_time
        geometric_series_sum_factor = (ONE - (daily_value_discount ** duration_to_sell)) / (
                1 - daily_value_discount)
        return value_per_day * geometric_series_sum_factor * lead_time_factor

    def reset_id(self):
        super(Inventory, self).reset_id()
        self.product.reset_id()
        for batch in self.batches:
            batch.reset_id()

    def copy_id(self, source: Inventory):
        super(Inventory, self).copy_id(source)
        self.product.copy_id(source.product)
        for i in range(len(self.batches)):
            self.batches[i].copy_id(source.batches[i])
