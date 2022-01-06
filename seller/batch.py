import math
from dataclasses import dataclass
from typing import Optional

from autologging import logged, traced

from common import constants
from common.context import DataGenerator
from common.primitives import Primitive
from common.util import Percent, Date, Duration, Stock, Dollar, min_max, Ratio
from seller.product import Product


@dataclass
class PurchaseOrder:
    stock: Stock
    upfront_cost: Dollar
    post_manufacturing_cost: Dollar


@traced
@logged
class Batch(Primitive):
    def __init__(self, data_generator: DataGenerator, product: Product, shipping_duration: Duration,
                 out_of_stock_rate: Percent, inventory_turnover_ratio: Ratio, roas: Ratio, organic_rate: Percent,
                 growth_rate: Percent, start_date: Date, stock: Stock):
        super(Batch, self).__init__(data_generator)
        self.product = product
        self.shipping_duration = shipping_duration
        self.lead_time = self.shipping_duration + self.product.manufacturing_duration
        self.stock = stock
        self.out_of_stock_rate = out_of_stock_rate
        self.inventory_turnover_ratio = inventory_turnover_ratio
        self.duration = math.ceil(constants.YEAR / self.inventory_turnover_ratio)
        self.roas = roas
        self.roas = roas
        self.organic_rate = organic_rate
        self.growth_rate = growth_rate
        self.start_date = start_date
        self.last_date = self.start_date + self.duration - 1
        self.purchase_order: Optional[PurchaseOrder] = None
        self.next_batch = None

    @classmethod
    def generate_simulated(cls, data_generator: DataGenerator, product: Optional[Product] = None,
                           previous: Optional['Batch'] = None):
        product = Batch.generate_product(data_generator, product, previous)
        shipping_duration = Batch.generate_shipping_duration(data_generator, product)
        lead_time = shipping_duration + product.manufacturing_duration
        inventory_turnover_ratio = Batch.generate_inventory_turnover_ratio(data_generator, lead_time, previous)
        stock = Batch.generate_initial_stock(data_generator, lead_time, product, previous)
        out_of_stock_rate = Batch.generate_out_of_stock_rate(data_generator, previous)
        growth_rate = Batch.generate_growth_rate(data_generator, previous)
        roas = Batch.generate_roas(data_generator, previous)
        organic_rate = Batch.generate_organic_rate(data_generator, previous, roas)
        start_date = (previous.last_date + 1) if previous else constants.START_DATE
        new_batch = Batch(
            data_generator, product, shipping_duration, out_of_stock_rate, inventory_turnover_ratio, roas,
            organic_rate, growth_rate, start_date, stock)
        if previous:
            previous.next_batch = new_batch
        return new_batch

    @classmethod
    def generate_product(cls, data_generator: DataGenerator, product: Product, previous: Optional['Batch']):
        assert product is None or previous is None or product == previous.product
        if previous:
            product = previous.product
        return product or Product.generate_simulated(data_generator)

    @classmethod
    def generate_organic_rate(cls, data_generator: DataGenerator, previous: Optional['Batch'], roas: Ratio) -> Percent:
        organic_rate = (
                           previous.organic_rate if previous else data_generator.organic_rate_median) * data_generator.normal_ratio(
            data_generator.organic_rate_std)
        if roas < data_generator.roas_median:
            organic_rate = max(data_generator.organic_rate_median, organic_rate)
        return organic_rate

    @classmethod
    def generate_roas(cls, data_generator: DataGenerator, previous: Optional['Batch']) -> Ratio:
        roas = (previous.roas if previous else data_generator.roas_median) * data_generator.normal_ratio(
            data_generator.roas_std)
        roas = min_max(roas, constants.MIN_ROAS, constants.MAX_ROAS)
        return roas

    @classmethod
    def generate_growth_rate(cls, data_generator: DataGenerator, previous: Optional['Batch']) -> Percent:
        return (
                   previous.growth_rate if previous else data_generator.growth_rate_avg) * data_generator.normal_ratio(
            data_generator.growth_rate_std, chance_positive=constants.SHARE_OF_GROWERS)

    @classmethod
    def generate_out_of_stock_rate(cls, data_generator: DataGenerator, previous: Optional['Batch']) -> Percent:
        return (
                   previous.out_of_stock_rate if previous else data_generator.out_of_stock_rate_median) * data_generator.normal_ratio(
            data_generator.out_of_stock_rate_std, chance_positive=0.2)

    @classmethod
    def generate_initial_stock(cls, data_generator: DataGenerator, lead_time: Duration, product: Product,
                               previous: Optional['Batch']) -> Stock:
        return 0 if previous else Stock(
            max(lead_time + 1, product.min_purchase_order_size) * data_generator.normal_ratio(
                data_generator.initial_stock_std, chance_positive=1))

    @classmethod
    def generate_inventory_turnover_ratio(cls, data_generator: DataGenerator, lead_time: Duration,
                                          previous: Optional['Batch']) -> Ratio:
        inventory_turnover_ratio = (
                                       previous.inventory_turnover_ratio if previous else
                                       data_generator.inventory_turnover_ratio_median) * data_generator.normal_ratio(
            data_generator.inventory_turnover_ratio_std)
        max_inventory_turnover_ratio = min(
            constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX, constants.YEAR / lead_time)
        inventory_turnover_ratio = min_max(
            inventory_turnover_ratio, constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_MIN,
            max_inventory_turnover_ratio)
        return inventory_turnover_ratio

    @classmethod
    def generate_shipping_duration(cls, data_generator: DataGenerator, product: Product) -> Duration:
        shipping_duration = Duration(
            data_generator.shipping_duration_avg * data_generator.normal_ratio(
                data_generator.shipping_duration_std, chance_positive=0.8))
        max_shipping_duration = constants.MAX_LEAD_TIME_DURATION - product.manufacturing_duration
        max_shipping_duration = min(constants.SHIPPING_DURATION_MAX, max_shipping_duration)
        shipping_duration = min_max(shipping_duration, constants.MIN_SHIPPING_DURATION, max_shipping_duration)
        return shipping_duration

    def gp_margin(self) -> Percent:
        return max(0.0, self.revenue_margin() - self.marketing_margin() - self.data_generator.sgna_ratio)

    def marketing_margin(self) -> Percent:
        return (self.acos() / self.product.price) * (1 - self.organic_rate)

    def acos(self) -> Dollar:
        return self.product.price / self.roas

    def get_manufacturing_done_date(self) -> Optional[Date]:
        if self.purchase_order is None:
            return None
        return self.get_purchase_order_start_date() + self.product.manufacturing_duration

    def get_purchase_order_start_date(self) -> Date:
        return self.last_date - self.lead_time + 1

    def max_purchase_order(self) -> PurchaseOrder:
        stock = self.max_stock_for_next_purchase_order()
        upfront_cost, post_cost = self.product.purchase_order_cost(stock)
        return PurchaseOrder(stock, upfront_cost, post_cost)

    def max_stock_for_next_purchase_order(self):
        return max(
            self.product.min_purchase_order_size, Stock(
                self.sales_velocity() * self.lead_time * (1 + self.growth_rate)))

    def initiate_new_purchase_order(self, current_cash: Dollar) -> Optional[PurchaseOrder]:
        current_cash += constants.FLOAT_ADJUSTMENT
        new_purchase_order = self.max_purchase_order()
        if not self.can_afford_purchase_order(new_purchase_order, current_cash):
            stock = self.product.batch_size_from_cost(current_cash)
            upfront_cost, post_cost = self.product.purchase_order_cost(stock)
            new_purchase_order = PurchaseOrder(stock, upfront_cost, post_cost)
        if new_purchase_order.stock >= self.product.min_purchase_order_size:
            self.purchase_order = new_purchase_order
            if self.next_batch:
                self.next_batch.stock = self.purchase_order.stock
        return self.purchase_order

    def can_afford_purchase_order(self, purchase_order: PurchaseOrder, current_cash: Dollar) -> bool:
        if self.data_generator.conservative_cash_management:
            return purchase_order.upfront_cost + purchase_order.post_manufacturing_cost <= current_cash
        return purchase_order.post_manufacturing_cost <= current_cash

    def max_inventory_cost(self, day: Date) -> Dollar:
        if day == self.get_purchase_order_start_date():
            return self.max_purchase_order().upfront_cost
        elif day == self.get_manufacturing_done_date() and self.purchase_order:
            return self.purchase_order.post_manufacturing_cost
        return 0

    def inventory_cost(self, day: Date, current_cash: Dollar) -> Dollar:
        if day == self.get_purchase_order_start_date():
            self.initiate_new_purchase_order(current_cash)
            if self.purchase_order:
                return self.purchase_order.upfront_cost
            else:
                return 0
        elif day == self.get_manufacturing_done_date():
            return self.purchase_order.post_manufacturing_cost
        return 0

    def is_out_of_stock(self, day: Date) -> bool:
        return day - self.start_date >= self.duration_in_stock()

    def sales_velocity(self) -> float:
        return self.stock / (self.duration * (1 - self.out_of_stock_rate))

    def total_revenue_per_day(self, day: Date) -> Dollar:
        if self.is_out_of_stock(day):
            return 0
        return self.sales_velocity() * self.product.price

    def revenue_per_day(self, day: Date) -> Dollar:
        return self.total_revenue_per_day(day) * self.revenue_margin()

    @staticmethod
    def revenue_margin():
        return 1 - constants.MARKETPLACE_COMMISSION

    def profit_margin(self):
        return self.gp_margin() - self.product.cogs_margin

    def gp_per_day(self, day: Date) -> Dollar:
        return self.total_revenue_per_day(day) * self.gp_margin()

    def duration_in_stock(self) -> Duration:
        if self.sales_velocity() == 0:
            if self.stock > 0:
                return self.duration
            else:
                return 0
        return math.ceil(self.stock / self.sales_velocity() - constants.FLOAT_ADJUSTMENT)

    # at the beginning of the day
    def remaining_stock(self, day: Date) -> Stock:
        assert day >= self.start_date
        sales_duration = min(self.duration_in_stock(), day - self.start_date)
        sold_in_duration = Stock(self.sales_velocity() * sales_duration)
        return max(self.stock - sold_in_duration, 0)
