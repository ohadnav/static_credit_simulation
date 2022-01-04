import logging
import math
from dataclasses import dataclass
from typing import Optional

from autologging import logged, traced

from common import constants
from common.context import DataGenerator
from common.util import Percent, Date, Duration, Stock, Dollar
from common.primitives import Primitive
from seller.product import Product


@dataclass
class PurchaseOrder:
    stock: Stock
    upfront_cost: Dollar
    post_manufacturing_cost: Dollar


@traced
@logged
class Batch(Primitive):
    def __init__(self, data_generator: DataGenerator, product: Product, out_of_stock_ratio: Percent,
                 inventory_turnover_ratio: float, roas: float, organic_ratio: Percent, growth_rate: Percent,
                 stock: Optional[Stock], start_date: Date):
        super(Batch, self).__init__(data_generator)
        self.product = product
        self.stock = stock
        self.out_of_stock_ratio = out_of_stock_ratio
        self.inventory_turnover_ratio = inventory_turnover_ratio
        self.roas = roas
        self.roas = roas
        self.organic_ratio = organic_ratio
        self.growth_rate = growth_rate
        self.start_date = start_date
        self.purchase_order: Optional[PurchaseOrder] = None
        self.next_batch = None

    @classmethod
    def generate_simulated(cls, data_generator: DataGenerator, product: Optional[Product] = None,
                           previous: Optional['Batch'] = None):
        product = product or Product.generate_simulated(data_generator)
        inventory_turnover_ratio = (
                                       previous.inventory_turnover_ratio if previous else
                                       data_generator.inventory_turnover_ratio_median) * data_generator.normal_ratio(
            constants.INVENTORY_TURNOVER_RATIO_STD)
        inventory_turnover_ratio = min(inventory_turnover_ratio, constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX)
        inventory_turnover_ratio = min(inventory_turnover_ratio, constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX)
        stock = None if previous else Stock(
            max(product.lead_time() + 1, product.min_purchase_order_size) * data_generator.normal_ratio(
                constants.INITIAL_STOCK_STD, chance_positive=1))
        out_of_stock_ratio = (
                                 previous.out_of_stock_ratio if previous else data_generator.out_of_stock_ratio_median) * data_generator.normal_ratio(
            constants.OUT_OF_STOCK_STD, chance_positive=0.2)
        growth_rate = (
                          previous.growth_rate if previous else data_generator.expected_sales_growth) * data_generator.normal_ratio(
            std=constants.SALES_GROWTH_STD, chance_positive=constants.SHARE_OF_GROWERS)
        roas = (previous.roas if previous else data_generator.roas_median) * data_generator.normal_ratio(
            data_generator.roas_variance)
        organic_ratio = (
                            previous.organic_ratio if previous else data_generator.organic_ratio_median) * data_generator.normal_ratio(
            data_generator.organic_ratio_variance)
        start_date = (previous.start_date + previous.batch_duration()) if previous else 0
        new_batch = Batch(
            data_generator, product, out_of_stock_ratio, inventory_turnover_ratio, roas, organic_ratio, growth_rate,
            stock, start_date)
        if previous:
            previous.next_batch = new_batch
        return new_batch

    def gp_margin(self) -> Percent:
        return self.revenue_margin() - self.marketing_margin() - self.data_generator.sgna_ratio

    def marketing_margin(self) -> Percent:
        return (self.acos() / self.product.price) * (1 - self.organic_ratio)

    def acos(self) -> Dollar:
        return self.product.price / self.roas

    def get_manufacturing_done_date(self) -> Optional[Date]:
        if self.purchase_order is None:
            return None
        return self.get_purchase_order_start_date() + self.product.manufacturing_duration

    def get_purchase_order_start_date(self) -> Date:
        return self.last_date() - self.product.lead_time()

    def max_purchase_order(self) -> PurchaseOrder:
        stock = Stock(
            self.sales_velocity() * self.product.lead_time() * (1 + self.growth_rate))
        stock = max(self.product.min_purchase_order_size, stock)
        upfront_cost, post_cost = self.product.purchase_order_cost(stock)
        return PurchaseOrder(stock, upfront_cost, post_cost)

    def initiate_new_purchase_order(self, current_cash):
        new_purchase_order = self.max_purchase_order()
        if new_purchase_order.upfront_cost > current_cash:
            stock = self.product.batch_size_from_upfront_cost(current_cash)
            upfront_cost, post_cost = self.product.purchase_order_cost(stock)
            new_purchase_order = PurchaseOrder(stock, upfront_cost, post_cost)
        if new_purchase_order.stock > self.product.min_purchase_order_size:
            self.purchase_order = new_purchase_order

    def max_inventory_cost(self, day: Date) -> Dollar:
        if day == self.get_purchase_order_start_date():
            return self.max_purchase_order().upfront_cost
        elif day == self.get_manufacturing_done_date():
            return self.purchase_order.post_manufacturing_cost
        return 0

    def inventory_cost(self, day: Date, current_cash: Dollar) -> Dollar:
        if day == self.get_purchase_order_start_date():
            self.initiate_new_purchase_order(current_cash)
            return self.purchase_order.upfront_cost
        elif day == self.get_manufacturing_done_date():
            return self.purchase_order.post_manufacturing_cost
        return 0

    def batch_start_date(self):
        return self.batch_duration() - self.product.lead_time()

    def batch_duration(self) -> Duration:
        return constants.YEAR / self.inventory_turnover_ratio

    def is_out_of_stock(self, day: Date) -> bool:
        return day - self.start_date > self.duration_out_of_stock()

    def last_date(self) -> Date:
        return self.start_date + self.batch_duration()

    def sales_velocity(self) -> float:
        return self.stock / (self.batch_duration() * (1 - self.out_of_stock_ratio))

    def revenue_per_day(self, day: Date) -> Dollar:
        if self.is_out_of_stock(day):
            return 0
        return self.sales_velocity() * self.product.price * self.revenue_margin()

    @staticmethod
    def revenue_margin():
        return 1 - constants.MARKETPLACE_COMMISSION

    def gp_per_day(self, day: Date) -> Dollar:
        return self.revenue_per_day(day) * self.gp_margin()

    def duration_out_of_stock(self) -> Duration:
        duration_until_out_of_stock = math.ceil(self.stock / self.sales_velocity())
        return self.batch_duration() - duration_until_out_of_stock
