from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import fields, dataclass
from typing import List, MutableMapping, Optional

import dacite as dacite
import numpy as np
from joblib import delayed

from common import constants
from common.context import SimulationContext, DataGenerator
from common.enum import LoanSimulationType
from common.numbers import Float, Percent, Ratio, Dollar, O
from common.primitive import Primitive
from common.util import weighted_average, TqdmParallel, get_key_from_value
from finance.line_of_credit import LineOfCreditSimulation, DynamicLineOfCreditSimulation
from finance.loan_simulation import LoanSimulationResults, LoanSimulation, IncreasingRebateLoanSimulation, \
    NoCapitalLoanSimulation
from seller.merchant import Merchant


@dataclass(unsafe_hash=True)
class AggregatedLoanSimulationResults:
    revenues_cagr: Percent
    inventory_cagr: Percent
    net_cashflow_cagr: Percent
    valuation_cagr: Percent
    lender_profit: Dollar
    total_credit: Dollar
    debt_to_valuation: Percent
    apr: Percent
    bankruptcy_rate: Percent


LOAN_TYPES_MAPPING = {
    LoanSimulationType.INCREASING_REBATE: IncreasingRebateLoanSimulation,
    LoanSimulationType.DYNAMIC_LINE_OF_CREDIT: DynamicLineOfCreditSimulation,
    LoanSimulationType.LINE_OF_CREDIT: LineOfCreditSimulation,
    LoanSimulationType.NO_CAPITAL: NoCapitalLoanSimulation,
    LoanSimulationType.DEFAULT: LoanSimulation,
}


#

class LenderSimulationResults:
    def __init__(
            self, lender_profit: Dollar, sharpe: Ratio,
            all_merchants: AggregatedLoanSimulationResults, portfolio_merchants: AggregatedLoanSimulationResults):
        self.profit = lender_profit
        self.portfolio = portfolio_merchants
        self.all = all_merchants
        self.sharpe = sharpe

    def __eq__(self, other):
        if not isinstance(other, LenderSimulationResults):
            return False
        return self.profit == other.profit \
               and self.sharpe == other.sharpe \
               and self.all == other.all \
               and self.portfolio == other.portfolio

    def __str__(self):
        return f'Profit: {self.profit} sharpe: {self.sharpe} all_lsr: {self.all} portfolio: {self.portfolio}'

    def __repr__(self):
        return self.__str__()


class Lender(Primitive):
    def __init__(
            self, context: SimulationContext, data_generator: DataGenerator, merchants: List[Merchant],
            loan_type: LoanSimulationType = LoanSimulationType.DEFAULT):
        super(Lender, self).__init__(data_generator)
        self.merchants = merchants
        self.context = context
        self.simulation_results: Optional[LenderSimulationResults] = None
        self.loans: MutableMapping[Merchant, LoanSimulation] = {}
        self.risk_correlation: MutableMapping[str, MutableMapping[str, Percent]] = {}
        self.loan_type = loan_type

    @classmethod
    def generate_from_simulated_loans(cls, loans: List[LoanSimulation]) -> Lender:
        merchants = [loan.merchant for loan in loans]
        context = deepcopy(loans[0].context)
        context.loan_type = get_key_from_value(type(loans[0]), LOAN_TYPES_MAPPING)
        data_generator = loans[0].data_generator
        lender = Lender(context, data_generator, merchants)
        lender.loans = {loan.merchant: loan for loan in loans}
        lender.calculate_results()
        return lender

    @staticmethod
    def generate_loan(
            merchant: Merchant, context: SimulationContext, data_generator: DataGenerator,
            loan_type: LoanSimulationType) -> LoanSimulation:
        return LOAN_TYPES_MAPPING[loan_type](context, data_generator, merchant)

    def generate_loan_from_merchant(self, merchant: Merchant) -> LoanSimulation:
        return Lender.generate_loan(merchant, self.context, self.data_generator, self.loan_type)

    @staticmethod
    def aggregate_results(loan_results: List[LoanSimulationResults]) -> AggregatedLoanSimulationResults:
        result = {}
        for field in fields(LoanSimulationResults):
            if field.name == 'valuation':
                continue
            elif field.name == 'lender_profit':
                result[field.name] = Float.sum([lsr.lender_profit for lsr in loan_results])
            elif field.name == 'total_credit':
                result[field.name] = Float.sum([lsr.total_credit for lsr in loan_results])
            else:
                values = []
                weights = []
                for lsr in loan_results:
                    values.append(getattr(lsr, field.name))
                    weights.append(Float.min(lsr.valuation, constants.MAX_RESULTS_WEIGHT))
                result[field.name] = weighted_average(values, weights)
        return dacite.from_dict(AggregatedLoanSimulationResults, result)

    def calculate_sharpe(self, portfolio_results: List[LoanSimulationResults]) -> Ratio:
        aggregated = Lender.aggregate_results(portfolio_results)
        portfolio_return = aggregated.apr
        risk_free_return = self.context.cost_of_capital
        std = np.std([lsr.apr for lsr in portfolio_results])
        if std <= 0:
            return O
        sharpe = (portfolio_return - risk_free_return) / std
        return sharpe

    def calculate_correlation(self, simulation_result_field_name: str) -> MutableMapping[str, Percent]:
        correlations = {}
        lender_results = [getattr(lsr, simulation_result_field_name) for lsr in
            self.portfolio_loan_simulation_results()]
        for risk_field in vars(self.context.risk_context).keys():
            initial_risk_scores = [getattr(loan.underwriting.initial_risk_context, risk_field).score for loan in
                self.portfolio_loans()]
            correlation_coefficient = Percent(np.corrcoef(lender_results, initial_risk_scores)[0][1])
            correlations[risk_field] = correlation_coefficient if not math.isnan(correlation_coefficient) else O
        return correlations

    def underwriting_correlation(self):
        for field in fields(AggregatedLoanSimulationResults):
            self.risk_correlation[field.name] = self.calculate_correlation(field.name)

    def calculate_results(self):
        all_merchants = self.aggregate_results([loan.simulation_results for loan in self.loans.values()])
        portfolio_results = self.portfolio_loan_simulation_results()
        portfolio_merchants_agg_results = self.aggregate_results(portfolio_results)
        sharpe = self.calculate_sharpe(portfolio_results)
        self.simulation_results = LenderSimulationResults(
            portfolio_merchants_agg_results.lender_profit, sharpe, all_merchants, portfolio_merchants_agg_results)
        self.underwriting_correlation()

    def portfolio_loan_simulation_results(self) -> List[LoanSimulationResults]:
        return [loan.simulation_results for loan in self.loans.values() if loan.total_credit > 0]

    def portfolio_loans(self) -> List[LoanSimulation]:
        return [loan for loan in self.loans.values() if loan.total_credit > 0]

    def simulate(self):
        simulated_loans = TqdmParallel(desc=f'{self.id}({self.loan_type.value})', total=len(self.merchants))(
            delayed(self.simulate_merchant)(merchant) for merchant in self.merchants)
        for loan in simulated_loans:
            self.loans[loan.merchant] = loan
        self.calculate_results()

    def simulate_merchant(self, merchant: Merchant) -> LoanSimulation:
        loan = self.generate_loan_from_merchant(merchant)
        loan.simulate()
        return loan
