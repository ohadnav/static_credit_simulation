from typing import Optional, List

from autologging import logged, traced

from common import constants
from common.context import DataGenerator
from common.primitives import Primitive
from common.util import Percent, Date, Dollar, weighted_average, min_max
from seller.inventory import Inventory


@traced
@logged
class Merchant(Primitive):
    def __init__(self, data_generator: DataGenerator, inventories: List[Inventory],
                 account_suspension_chance: Percent):
        super(Merchant, self).__init__(data_generator)
        self.inventories = inventories
        self.account_suspension_chance = account_suspension_chance
        self.suspension_start_date: Optional[Date] = self.calculate_suspension_start_date()

    @classmethod
    def generate_simulated(cls, data_generator: DataGenerator, inventories: Optional[List[Inventory]] = None):
        num_products = round(data_generator.num_products * data_generator.normal_ratio())
        num_products = min_max(num_products, 1, data_generator.max_num_products)
        inventories = inventories or [Inventory.generate_simulated(data_generator) for _ in range(num_products)]
        account_suspension_chance = data_generator.account_suspension_chance * data_generator.normal_ratio()
        return Merchant(data_generator, inventories, account_suspension_chance)

    def calculate_suspension_start_date(self) -> Optional[Date]:
        suspension_date = None
        for i in range(constants.START_DATE, self.data_generator.simulated_duration + 1):
            if self.data_generator.random() < self.account_suspension_chance:
                suspension_date = i
        return suspension_date

    def annual_top_line(self, day: Date) -> Dollar:
        return sum([inventory.annual_top_line(day) for inventory in self.inventories])

    def is_suspended(self, day: Date):
        return self.suspension_start_date and \
               self.suspension_start_date <= day <= self.suspension_start_date + constants.ACCOUNT_SUSPENSION_DURATION - 1

    def gp_per_day(self, day: Date) -> Dollar:
        if self.is_suspended(day):
            return 0
        total_gp = sum([inventory.gp_per_day(day) for inventory in self.inventories])
        return total_gp

    def revenue_per_day(self, day: Date) -> Dollar:
        if self.is_suspended(day):
            return 0
        total_revenue = sum([inventory.revenue_per_day(day) for inventory in self.inventories])
        return total_revenue

    def max_inventory_cost(self, day: Date) -> Dollar:
        max_cost = sum([batch.max_inventory_cost(day) for batch in self.current_active_batches(day)])
        return max_cost

    def current_active_batches(self, day):
        return [inventory[day] for inventory in self.inventories if day in inventory]

    def inventory_cost(self, day: Date, current_cash: Dollar) -> Dollar:
        total_to_pay = 0.0
        available_cash = max(0.0, current_cash - self.cashflow_buffer(day))
        for batch in self.current_active_batches(day):
            batch_cost = batch.inventory_cost(day, available_cash)
            total_to_pay += batch_cost
            available_cash -= batch_cost
        return total_to_pay

    def cashflow_buffer(self, day: Date) -> Dollar:
        # TODO: embed cashdlow forecasting into the calculation
        committed_purchase_orders = [batch.purchase_order for batch in self.current_active_batches(day) if
                                     batch.purchase_order]
        total_future_costs = sum([po.post_manufacturing_cost for po in committed_purchase_orders])
        return total_future_costs

    def valuation(self, day: Date, net_cashflow: Dollar) -> Dollar:
        return net_cashflow + sum([inventory.valuation(day) for inventory in self.inventories])

    def inventory_value(self, day: Date) -> Dollar:
        return sum([inventory.current_inventory_valuation(day) for inventory in self.inventories])

    def organic_ratio(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        organic_ratios = [inventory[day].organic_ratio for inventory in self.inventories]
        return weighted_average(organic_ratios, top_lines)

    def out_of_stock_ratio(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        out_of_stock_ratios = [inventory[day].out_of_stock_ratio for inventory in self.inventories]
        return weighted_average(out_of_stock_ratios, top_lines)

    def profit_margin(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        profit_margins = [inventory[day].profit_margin() for inventory in self.inventories]
        return weighted_average(profit_margins, top_lines)

    def inventory_turnover_ratio(self, day: Date) -> float:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        ratios = [inventory[day].inventory_turnover_ratio for inventory in self.inventories]
        return weighted_average(ratios, top_lines)

    def roas(self, day: Date) -> float:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        ratios = [inventory[day].roas for inventory in self.inventories]
        return weighted_average(ratios, top_lines)
