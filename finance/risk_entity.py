from abc import ABC

from common.local_numbers import Percent, Ratio, Date


class RiskEntity(ABC):
    # TODO: calculate amount based on historical values
    def get_out_of_stock_rate(self, day: Date) -> Percent: pass

    def get_inventory_turnover_ratio(self, day: Date) -> Ratio: pass

    def get_adjusted_profit_margin(self, day: Date) -> Percent: pass

    def get_roas(self, day: Date) -> Ratio: pass

    def get_organic_rate(self, day: Date) -> Percent: pass
