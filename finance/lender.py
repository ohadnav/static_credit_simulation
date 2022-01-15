import math
from dataclasses import fields, dataclass
from typing import List, MutableMapping, Optional

import dacite as dacite
import numpy as np
from joblib import delayed

from common.constants import LoanSimulationType
from common.context import SimulationContext, DataGenerator
from common.primitive import Primitive
from common.util import Dollar, weighted_average, Percent, TqdmParallel, Float, Ratio, O
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
        self.lender_profit = lender_profit
        self.sharpe = sharpe
        self.all_merchants = all_merchants
        self.portfolio_merchants = portfolio_merchants

    def __eq__(self, other):
        if not isinstance(other, LenderSimulationResults):
            return False
        return self.lender_profit == other.lender_profit \
               and self.sharpe == other.sharpe \
               and self.all_merchants == other.all_merchants \
               and self.portfolio_merchants == other.portfolio_merchants

    def __str__(self):
        return f'GP: {self.lender_profit} sharpe: {self.sharpe} all_lsr: {self.all_merchants} portfolio: ' \
               f'{self.portfolio_merchants}'


class Lender(Primitive):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchants: List[Merchant]):
        super(Lender, self).__init__(data_generator)
        self.merchants = merchants
        self.context = context
        self.simulation_results: Optional[LenderSimulationResults] = None
        self.loans: MutableMapping[Merchant, LoanSimulation] = {}
        self.risk_correlation: MutableMapping[str, MutableMapping[str, Percent]] = {}

    @staticmethod
    def loan_from_merchant(
            merchant: Merchant, context: SimulationContext, data_generator: DataGenerator,
            loan_type: LoanSimulationType) -> LoanSimulation:
        return LOAN_TYPES_MAPPING[loan_type](context, data_generator, merchant)

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
                    weights.append(lsr.valuation)
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
            correlation_coefficient = np.corrcoef(lender_results, initial_risk_scores)[0][1]
            correlations[risk_field] = correlation_coefficient if not math.isnan(correlation_coefficient) else 0
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
        simulated_loans = TqdmParallel(desc=f'{self.id}({self.context.loan_type.value})', total=len(self.merchants))(
            delayed(self.simulate_merchant)(merchant) for merchant in self.merchants)
        for loan in simulated_loans:
            self.loans[loan.merchant] = loan
        self.calculate_results()

    def simulate_merchant(self, merchant: Merchant) -> LoanSimulation:
        loan = Lender.loan_from_merchant(
            merchant, self.context, self.data_generator, self.context.loan_type)
        loan.simulate()
        return loan
