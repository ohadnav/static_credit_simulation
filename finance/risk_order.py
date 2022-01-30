from __future__ import annotations

from typing import Optional, List

from common import constants
from common.numbers import Percent, O, Float, Int, O_INT, HALF, TWO, FloatRange

DEFAULT_RANGES = [
    FloatRange(max_value=O), FloatRange(O, HALF), FloatRange(HALF, TWO),
    FloatRange(TWO, Percent(constants.WHALE_GROWTH_CAGR)), FloatRange(Percent(constants.WHALE_GROWTH_CAGR))]


class RiskOrder:
    def __init__(self, cagrs: Optional[List[Float]] = None):
        self.risk_orders = self.init_risk_orders(cagrs) if cagrs else DEFAULT_RANGES

    def count_per_order(self, cagrs: List[Float]) -> List[Int]:
        counts = [O_INT for _ in range(len(self.risk_orders))]
        for cagr in cagrs:
            counts[self.get_order(cagr)] += 1
        return counts

    def init_risk_orders(self, cagrs: List[Float]) -> List[FloatRange]:
        mid_cagrs = self.get_sorted_mid_cagrs(cagrs)
        cur_cagr = O
        risk_orders = [FloatRange(max_value=O)]
        num_mid_buckets = Int.min(self.default_num_mid_buckets(), len(mid_cagrs))
        for i in range(num_mid_buckets - 1):
            next_cagr = mid_cagrs[(i + 1) * len(mid_cagrs) // num_mid_buckets]
            risk_orders.append(FloatRange(cur_cagr, next_cagr))
            cur_cagr = next_cagr
        risk_orders.append(FloatRange(risk_orders[-1].max_value, Percent(constants.WHALE_GROWTH_CAGR)))
        risk_orders.append(FloatRange(Percent(constants.WHALE_GROWTH_CAGR)))
        return risk_orders

    @staticmethod
    def get_sorted_mid_cagrs(cagrs):
        mid_cagrs = filter(lambda cagr: O <= cagr < constants.WHALE_GROWTH_CAGR, cagrs)
        sorted_cagr = sorted(mid_cagrs)
        return sorted_cagr

    @staticmethod
    def default_num_mid_buckets():
        return constants.NUM_RISK_ORDERS - 2

    def next_order(self, order: Int) -> Int:
        if order != len(self.risk_orders) - 1:
            return order + 1
        return order

    def prev_order(self, order: Int) -> Int:
        if order != O_INT:
            return order - 1
        return order

    def get_order(self, cagr: Percent) -> Int:
        if cagr < self.risk_orders[0].max_value:
            return O_INT
        for i, risk_order in enumerate(reversed(self.risk_orders[1:])):
            if cagr >= risk_order.min_value:
                return Int(len(self.risk_orders) - i - 1)

    def __eq__(self, other: RiskOrder) -> bool:
        return self.risk_orders == other.risk_orders
