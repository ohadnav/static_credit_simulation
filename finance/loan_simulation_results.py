from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields

from common.numbers import Dollar, Percent, Int


@dataclass(unsafe_hash=True)
class LoanSimulationResults:
    valuation: Dollar
    revenue_cagr: Percent
    total_revenue: Dollar
    inventory_cagr: Percent
    net_cashflow_cagr: Percent
    valuation_cagr: Percent
    lender_profit: Dollar
    total_credit: Dollar
    lender_profit_margin: Percent
    total_interest: Dollar
    debt_to_valuation: Percent
    apr: Percent
    bankruptcy_rate: Percent
    hyper_growth_rate: Percent
    duration_in_debt_rate: Percent
    num_loans: Int

    def __str__(self):
        s = []
        for k, v in vars(self).items():
            s.append(f'{k}={v.__str__()}')
        return ' '.join(s)

    def __repr__(self):
        return self.__str__()

    def __sub__(self, other: LoanSimulationResults):
        assert isinstance(other, LoanSimulationResults)
        sub_result = deepcopy(self)
        for field in fields(LoanSimulationResults):
            value_self = getattr(self, field.name)
            value_other = getattr(other, field.name)
            setattr(sub_result, field.name, value_self - value_other)
        return sub_result
