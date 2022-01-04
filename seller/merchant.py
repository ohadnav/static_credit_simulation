from typing import Optional, List, Any

from autologging import logged, traced

from common import constants
from common.context import DataGenerator
from common.util import Percent, Date, Dollar
from common.primitives import Primitive
from seller.inventory import Inventory
from seller.product import Product
from seller.batch import Batch


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
    def generate_simulated(cls, data_generator: DataGenerator,
                           products: Optional[List[Product]] = None, inventories: Optional[List[Inventory]] = None):
        products = products or [Product.generate_simulated(data_generator) for _ in range(data_generator.num_products)]
        inventories = inventories or [Inventory.generate_simulated(data_generator, product) for product in products]
        account_suspension_chance = data_generator.account_suspension_chance * data_generator.normal_ratio()
        return Merchant(data_generator, inventories, account_suspension_chance)

    def calculate_suspension_start_date(self) -> Optional[Date]:
        day = constants.YEAR
        for i in range(constants.YEAR):
            if self.data_generator.random() < self.account_suspension_chance:
                day = i
        return day if day != constants.YEAR else None

    def annual_top_line(self, day: Date) -> Dollar:
        return sum([inventory.annual_top_line(day) for inventory in self.inventories])

    def is_suspended(self, day: Date):
        return self.suspension_start_date and self.suspension_start_date <= day <=\
               self.suspension_start_date + constants.ACCOUNT_SUSPENSION_DURATION

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

    def get_all_batches(self) -> List[Batch]:
        return [batch for inventory in self.inventories for batch in inventory.batches]

    def max_inventory_cost(self, day: Date) -> Dollar:
        current_batches = [inventory.current_batch(day) for inventory in self.inventories]
        max_cost = sum([batch.max_inventory_cost(day) for batch in current_batches])
        return max_cost

    def inventory_cost(self, day: Date, current_cash: Dollar) -> Dollar:
        current_batches = [inventory.current_batch(day) for inventory in self.inventories]
        total_to_pay = 0.0
        for batch in current_batches:
            total_to_pay += batch.inventory_cost(day, current_cash)
            current_cash -= total_to_pay
        return total_to_pay

    def valuation(self, day: Date, net_cashflow: Dollar) -> Dollar:
        return net_cashflow + sum([inventory.valuation(day) for inventory in self.inventories])

    def inventory_value(self, day: Date) -> Dollar:
        pass

    def organic_ratio(self, day: Date) -> Percent:
        pass

    def out_of_stock(self, day: Date) -> Percent:
        pass

    def profit_margin(self, day: Date) -> Percent:
        pass

    def inventory_turnover_ratio(self, day: Date) -> float:
        pass

    def roas(self, day: Date) -> float:
        pass

    def debt_to_inventory(self, day: Date) -> Percent:
        pass

