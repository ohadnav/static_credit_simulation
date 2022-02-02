from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Optional, List

import dacite

import constants
from common.local_numbers import Dollar, Percent, Int, Float, O, ONE, TWO
from util import inherits_from, weighted_average, min_max


@dataclass(unsafe_hash=True)
class LoanSimulationResults:
    valuation: Optional[Dollar]
    revenue_cagr: Percent
    annual_revenue: Dollar
    recent_revenue: Dollar
    projected_cagr: Percent
    inventory_cagr: Percent
    net_cashflow_cagr: Percent
    valuation_cagr: Percent
    lender_profit: Dollar
    total_credit: Dollar
    lender_profit_margin: Percent
    total_interest: Dollar
    debt_to_valuation: Percent
    effective_apr: Percent
    bankruptcy_rate: Percent
    hyper_growth_rate: Percent
    duration_in_debt_rate: Percent
    duration_finished_rate: Percent
    num_loans: Int

    def __str__(self):
        s = []
        for k, v in vars(self).items():
            s.append(f'{k}={v.__str__()}')
        return ' '.join(s)

    def __repr__(self):
        return self.__str__()

    def __sub__(self, other: LoanSimulationResults):
        assert inherits_from(type(other), LoanSimulationResults.__name__)
        sub_result = deepcopy(self)
        for field in fields(LoanSimulationResults):
            value_self = getattr(self, field.name)
            value_other = getattr(other, field.name)
            setattr(sub_result, field.name, value_self - value_other)
        return sub_result

    @classmethod
    def generate_from_float(cls, f: Float) -> LoanSimulationResults:
        result = {}
        for field in fields(LoanSimulationResults):
            result[field.name] = f
        result['num_loans'] = Int(f)
        return dacite.from_dict(LoanSimulationResults, result)


O_LSR = LoanSimulationResults.generate_from_float(O)
ONE_LSR = LoanSimulationResults.generate_from_float(ONE)
TWO_LSR = LoanSimulationResults.generate_from_float(TWO)

WEIGHT_FIELD = 'annual_revenue'
SUM_FIELDS = ['total_credit', 'lender_profit', 'total_interest', 'annual_revenue', 'valuation', 'recent_revenue']
NO_WEIGHTS_FIELDS = ['bankruptcy_rate', 'hyper_growth_rate', 'duration_in_debt_rate', 'duration_finished_rate']


@dataclass(unsafe_hash=True)
class AggregatedLoanSimulationResults(LoanSimulationResults):
    approval_rate: Percent
    num_merchants: Int
    num_loans: Float

    @classmethod
    def generate_from_list(
            cls, simulations_results: List[LoanSimulationResults],
            num_merchants: int) -> AggregatedLoanSimulationResults:
        result = {'num_merchants': Int(len(simulations_results)),
            'approval_rate': Percent(len(simulations_results) / num_merchants)}
        for field in fields(LoanSimulationResults):
            values = [getattr(lsr, field.name) for lsr in simulations_results]
            if field.name in SUM_FIELDS:
                result[field.name] = Float.sum(values)
            elif field.name in NO_WEIGHTS_FIELDS:
                result[field.name] = Float.mean(values)
            else:
                weights = [min_max(lsr.valuation, ONE, constants.MAX_RESULTS_WEIGHT) for lsr in simulations_results]
                result[field.name] = weighted_average(values, weights)
        return dacite.from_dict(AggregatedLoanSimulationResults, result)

    @classmethod
    def generate_from_numbers(
            cls, regular_field: Float, sum_field: Float, no_weight_field: Float, num_merchants: Int,
            approval_rate: Float) -> AggregatedLoanSimulationResults:
        result = {'num_merchants': num_merchants, 'approval_rate': approval_rate}
        for field in fields(LoanSimulationResults):
            if field.name in SUM_FIELDS:
                result[field.name] = sum_field
            elif field.name in NO_WEIGHTS_FIELDS:
                result[field.name] = no_weight_field
            else:
                result[field.name] = regular_field
        return dacite.from_dict(AggregatedLoanSimulationResults, result)
