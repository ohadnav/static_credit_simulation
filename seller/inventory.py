import logging
from typing import Optional, List

from autologging import logged, traced

from common import constants
from common.context import DataGenerator
from common.util import Date, Dollar
from common.primitives import Primitive
from seller.product import Product
from seller.batch import Batch


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
        total_duration = batches[0].batch_duration()
        while total_duration < constants.SIMULATION_DURATION:
            next_batch = Batch.generate_simulated(data_generator, product, batches[-1])
            total_duration += next_batch.batch_duration()
            batches.append(next_batch)
        new_inventory = Inventory(data_generator, product, batches)
        return new_inventory

    def current_batch(self, day: Date) -> Batch:
        return [batch for batch in self.batches if batch.start_date <=day <= batch.last_date()][0]

    def annual_top_line(self, day: Date) -> Dollar:
        return self.current_batch(day).inventory_turnover_ratio * self.current_batch(day).stock * self.product.price

    def gp_per_day(self, day: Date) -> Dollar:
        return self.current_batch(day).gp_per_day(day)

    def revenue_per_day(self, day: Date) -> Dollar:
        return self.current_batch(day).revenue_per_day(day)

    def valuation(self, day: Date) -> Dollar:
        pass