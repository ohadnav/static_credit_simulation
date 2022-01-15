from __future__ import annotations

from random import randint
from typing import Optional, List

from common import constants
from common.context import DataGenerator
from common.primitive import Primitive
from common.util import Percent, Date, Dollar, weighted_average, min_max, Ratio, O, Float
from seller.batch import Batch
from seller.inventory import Inventory


class Merchant(Primitive):
    def __init__(
            self, data_generator: DataGenerator, inventories: List[Inventory],
            suspension_start_date: Optional[Date]):
        super(Merchant, self).__init__(data_generator)
        self.inventories = inventories
        self.suspension_start_date: Optional[Date] = suspension_start_date

    @classmethod
    def generate_simulated(
            cls, data_generator: DataGenerator, inventories: Optional[List[Inventory]] = None) -> Merchant:
        num_products = round(data_generator.num_products * data_generator.normal_ratio())
        num_products = min_max(num_products, 1, data_generator.max_num_products)
        inventories = inventories or [Inventory.generate_simulated(data_generator) for _ in range(num_products)]
        account_suspension_date = Merchant.calculate_suspension_start_date(data_generator)
        return Merchant(data_generator, inventories, account_suspension_date)

    @classmethod
    def calculate_suspension_start_date(cls, data_generator: DataGenerator) -> Optional[Date]:
        suspension_start_date = None
        if data_generator.random() < data_generator.account_suspension_chance:
            suspension_start_date = randint(constants.START_DATE, data_generator.simulated_duration)
        return suspension_start_date

    def annual_top_line(self, day: Date) -> Dollar:
        return Float.sum([inventory.annual_top_line(day) for inventory in self.inventories])

    def is_suspended(self, day: Date):
        # TODO: push all inventory dates by constants.ACCOUNT_SUSPENSION_DURATION to better simulate suspension
        return self.suspension_start_date and \
               self.suspension_start_date <= day <= self.suspension_start_date + \
               constants.ACCOUNT_SUSPENSION_DURATION - 1

    def gp_per_day(self, day: Date) -> Dollar:
        if self.is_suspended(day):
            return O
        total_gp = Float.sum([inventory.gp_per_day(day) for inventory in self.inventories])
        return total_gp

    def revenue_per_day(self, day: Date) -> Dollar:
        if self.is_suspended(day):
            return O
        total_revenue = Float.sum([inventory.revenue_per_day(day) for inventory in self.inventories])
        return total_revenue

    def max_cash_needed(self, day: Date) -> Dollar:
        max_cost = Float.sum([batch.max_cash_needed(day) for batch in self.current_batches(day)])
        return max_cost

    def current_batches(self, day: Date) -> List[Batch]:
        return [inventory[day] for inventory in self.inventories]

    def inventory_cost(self, day: Date, current_cash: Dollar) -> Dollar:
        total_to_pay = O
        committed = self.committed_purchase_orders(day)
        cash_for_new_orders = Float.max(O, current_cash - committed)
        for batch in self.current_batches(day):
            # TODO: allocate budget per profitable product lines
            batch_cost = batch.inventory_cost(day, cash_for_new_orders)
            if batch_cost > O:
                total_to_pay += batch_cost
                cash_for_new_orders -= batch.purchase_order.total_cost()
        return total_to_pay

    def committed_purchase_orders(self, day: Date) -> Dollar:
        # TODO: embed cashdlow forecasting into the calculation
        committed_purchase_orders = [batch.purchase_order for batch in self.current_batches(day) if
            batch.purchase_order and day <= batch.get_manufacturing_done_date()]
        total_committed_costs = Float.sum([po.post_manufacturing_cost for po in committed_purchase_orders])
        return total_committed_costs

    def has_future_revenue(self, day: Date) -> bool:
        for batch in self.current_batches(day):
            if batch.has_future_revenue(day):
                return True
        return False

    def valuation(self, day: Date, net_cashflow: Dollar) -> Dollar:
        return net_cashflow + Float.sum([inventory.valuation(day) for inventory in self.inventories])

    def inventory_value(self, day: Date) -> Dollar:
        return Float.sum([inventory.current_inventory_valuation(day) for inventory in self.inventories])

    def organic_rate(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        organic_rates = [inventory[day].organic_rate for inventory in self.inventories]
        return weighted_average(organic_rates, top_lines)

    def out_of_stock_rate(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        out_of_stock_rates = [inventory[day].out_of_stock_rate for inventory in self.inventories]
        return weighted_average(out_of_stock_rates, top_lines)

    def profit_margin(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        profit_margins = [inventory[day].profit_margin() for inventory in self.inventories]
        return weighted_average(profit_margins, top_lines)

    def adjusted_profit_margin(self, day: Date) -> Percent:
        return self.profit_margin(day) + constants.PROFIT_MARGIN_ADJUSTMENT

    def inventory_turnover_ratio(self, day: Date) -> Ratio:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        ratios = [inventory[day].inventory_turnover_ratio for inventory in self.inventories]
        return weighted_average(ratios, top_lines)

    def roas(self, day: Date) -> Ratio:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        ratios = [inventory[day].roas for inventory in self.inventories]
        return weighted_average(ratios, top_lines)
