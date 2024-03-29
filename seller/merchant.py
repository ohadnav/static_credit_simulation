from __future__ import annotations

from random import randint
from typing import Optional, List

from common import constants
from common.context import DataGenerator
from common.local_numbers import Float, Percent, Ratio, Date, Dollar, O, Int
from common.primitive import Primitive
from common.util import weighted_average, min_max
from finance.risk_entity import RiskEntity
from seller.batch import Batch
from seller.inventory import Inventory


class Merchant(Primitive, RiskEntity):
    def __init__(
            self, data_generator: DataGenerator, inventories: List[Inventory],
            suspension_start_date: Optional[Date]):
        super(Merchant, self).__init__(data_generator)
        self.inventories = inventories
        self.suspension_start_date: Optional[Date] = suspension_start_date

    @classmethod
    def generate_simulated(
            cls, data_generator: DataGenerator, inventories: Optional[List[Inventory]] = None) -> Merchant:
        num_products = cls.generate_num_products(data_generator)
        sgna_rate = Batch.generate_sgna_rate(data_generator)
        inventories = inventories or [Inventory.generate_simulated(data_generator, sgna_rate) for _ in
            range(num_products)]
        account_suspension_date = Merchant.calculate_suspension_start_date(data_generator)
        return Merchant(data_generator, inventories, account_suspension_date)

    @classmethod
    def generate_num_products(cls, data_generator: DataGenerator):
        num_products = round(data_generator.num_products * data_generator.normal_ratio(data_generator.num_products_std))
        num_products = min_max(num_products, 1, data_generator.max_num_products)
        return num_products

    @classmethod
    def calculate_suspension_start_date(cls, data_generator: DataGenerator) -> Optional[Date]:
        suspension_start_date = None
        if data_generator.random() < data_generator.account_suspension_chance:
            suspension_start_date = randint(data_generator.start_date, data_generator.simulated_duration)
        return suspension_start_date

    def num_products(self, *args, **kwargs) -> Int:
        return Int(len(self.inventories))

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

    def batch_profit_margin(self, batch: Batch) -> Percent:
        return batch.profit_margin()

    def batches_with_orders(self, day: Date) -> List[Batch]:
        batches = [batch for batch in self.current_batches(day) if batch.max_cash_needed(day) > O]
        batches.sort(key=self.batch_profit_margin, reverse=True)
        return batches

    def inventory_cost(self, day: Date, current_cash: Dollar) -> Dollar:
        total_to_pay = O
        committed = self.committed_purchase_orders(day)
        cash_for_new_orders = Float.max(O, current_cash - committed)
        for batch in self.batches_with_orders(day):
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

    def get_organic_rate(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        organic_rates = [inventory[day].organic_rate for inventory in self.inventories]
        return weighted_average(organic_rates, top_lines)

    def get_out_of_stock_rate(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        out_of_stock_rates = [inventory[day].out_of_stock_rate for inventory in self.inventories]
        return weighted_average(out_of_stock_rates, top_lines)

    def profit_margin(self, day: Date) -> Percent:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        profit_margins = [inventory[day].profit_margin() for inventory in self.inventories]
        return weighted_average(profit_margins, top_lines)

    def get_adjusted_profit_margin(self, day: Date) -> Percent:
        return self.profit_margin(day) + constants.PROFIT_MARGIN_ADJUSTMENT

    def get_inventory_turnover_ratio(self, day: Date) -> Ratio:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        ratios = [inventory[day].inventory_turnover_ratio for inventory in self.inventories]
        return weighted_average(ratios, top_lines)

    def get_roas(self, day: Date) -> Ratio:
        top_lines = [inventory.annual_top_line(day) for inventory in self.inventories]
        ratios = [inventory[day].roas for inventory in self.inventories]
        return weighted_average(ratios, top_lines)

    def reset_id(self):
        super(Merchant, self).reset_id()
        for inventory in self.inventories:
            inventory.reset_id()

    def copy_id(self, source: Merchant):
        super(Merchant, self).copy_id(source)
        for i in range(len(self.inventories)):
            self.inventories[i].copy_id(source.inventories[i])
