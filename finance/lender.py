from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import fields, dataclass
from typing import List, MutableMapping, Optional, Mapping

import dacite as dacite
import numpy as np
from joblib import delayed

from common import constants
from common.context import SimulationContext, DataGenerator
from common.enum import LoanSimulationType
from common.numbers import Float, Percent, Ratio, Dollar, O, Int
from common.primitive import Primitive
from common.util import weighted_average, TqdmParallel, get_key_from_value
from finance.line_of_credit import LineOfCreditSimulation, DynamicLineOfCreditSimulation, InvoiceFinancingSimulation
from finance.loan_simulation import LoanSimulationResults, LoanSimulation, IncreasingRebateLoanSimulation, \
    NoCapitalLoanSimulation
from seller.merchant import Merchant


@dataclass(unsafe_hash=True)
class AggregatedLoanSimulationResults:
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
    acceptance_rate: Percent
    num_merchants: Int
    num_loans: Float


WEIGHT_FIELD = 'valuation'
SUM_FIELDS = ['total_credit', 'lender_profit', 'total_interest', 'total_revenue']
NO_WEIGHTS_FIELDS = ['bankruptcy_rate', 'hyper_growth_rate', 'duration_in_debt_rate']

LOAN_TYPES_MAPPING = {
    LoanSimulationType.INCREASING_REBATE: IncreasingRebateLoanSimulation,
    LoanSimulationType.DYNAMIC_LINE_OF_CREDIT: DynamicLineOfCreditSimulation,
    LoanSimulationType.LINE_OF_CREDIT: LineOfCreditSimulation,
    LoanSimulationType.NO_CAPITAL: NoCapitalLoanSimulation,
    LoanSimulationType.DEFAULT: LoanSimulation,
    LoanSimulationType.INVOICE_FINANCING: InvoiceFinancingSimulation
}


#

class LenderSimulationResults:
    def __init__(
            self, sharpe: Ratio, all_merchants: AggregatedLoanSimulationResults,
            funded_merchants: AggregatedLoanSimulationResults):
        self.funded = funded_merchants
        self.all = all_merchants
        self.sharpe = sharpe

    def __eq__(self, other):
        if not isinstance(other, LenderSimulationResults):
            return False
        return self.sharpe == other.sharpe \
               and self.all == other.all \
               and self.funded == other.funded

    def __str__(self):
        return f'funded: {self.funded} all_lsr: {self.all} sharpe: {self.sharpe}'

    def __repr__(self):
        return self.__str__()


class Lender(Primitive):
    def __init__(
            self, context: SimulationContext, data_generator: DataGenerator, merchants: List[Merchant],
            loan_type: LoanSimulationType = LoanSimulationType.DEFAULT,
            reference_loans: Optional[Mapping[Merchant, LoanSimulation]] = None):
        super(Lender, self).__init__(data_generator)
        self.merchants = merchants
        self.context = context
        self.simulation_results: Optional[LenderSimulationResults] = None
        self.loans: MutableMapping[Merchant, LoanSimulation] = {}
        self.risk_correlation: MutableMapping[str, MutableMapping[str, Percent]] = {}
        self.loan_type = loan_type
        self.reference_loans = reference_loans

    @classmethod
    def generate_from_simulated_loans(cls, loans: List[LoanSimulation]) -> Lender:
        merchants = [loan.merchant for loan in loans]
        context = deepcopy(loans[0].context)
        loan_type = get_key_from_value(type(loans[0]), LOAN_TYPES_MAPPING)
        data_generator = loans[0].data_generator
        lender = Lender(context, data_generator, merchants, loan_type)
        lender.loans = {loan.merchant: loan for loan in loans}
        lender.calculate_results()
        return lender

    @classmethod
    def generate_from_reference_loans(cls, loans: List[LoanSimulation]) -> Lender:
        merchants = [loan.merchant for loan in loans]
        reference_loans = {loan.merchant: loan for loan in loans}
        context = loans[0].context
        loan_type = get_key_from_value(type(loans[0]), LOAN_TYPES_MAPPING)
        data_generator = loans[0].data_generator
        lender = Lender(context, data_generator, merchants, loan_type, reference_loans)
        return lender

    @staticmethod
    def generate_loan(
            merchant: Merchant, context: SimulationContext, data_generator: DataGenerator,
            loan_type: LoanSimulationType, reference_loan: Optional[LoanSimulation]) -> LoanSimulation:
        return LOAN_TYPES_MAPPING[loan_type](context, data_generator, merchant, reference_loan)

    def generate_loan_from_merchant(self, merchant: Merchant) -> LoanSimulation:
        reference_loan = self.reference_loans[merchant] if self.reference_loans else None
        return Lender.generate_loan(merchant, self.context, self.data_generator, self.loan_type, reference_loan)

    def aggregate_results(self, loan_results: List[LoanSimulationResults]) -> AggregatedLoanSimulationResults:
        result = {'num_merchants': Int(len(loan_results)),
            'acceptance_rate': Percent(len(loan_results) / len(self.merchants))}
        for field in fields(LoanSimulationResults):
            if field.name == WEIGHT_FIELD:
                continue
            values = [getattr(lsr, field.name) for lsr in loan_results]
            if field.name in SUM_FIELDS:
                result[field.name] = Float.sum(values)
            elif field.name in NO_WEIGHTS_FIELDS:
                result[field.name] = Float.average(values)
            else:
                weights = [Float.min(lsr.valuation, constants.MAX_RESULTS_WEIGHT) for lsr in loan_results]
                result[field.name] = weighted_average(values, weights)
        return dacite.from_dict(AggregatedLoanSimulationResults, result)

    def calculate_sharpe(self, portfolio_results: List[LoanSimulationResults]) -> Ratio:
        aggregated = self.aggregate_results(portfolio_results)
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
            self.funded_merchants_simulation_results()]
        for risk_field in vars(self.context.risk_context).keys():
            initial_risk_scores = [getattr(loan.underwriting.initial_risk_context, risk_field).score for loan in
                self.funded_merchants_loans()]
            correlation_coefficient = Percent(np.corrcoef(lender_results, initial_risk_scores)[0][1])
            correlations[risk_field] = correlation_coefficient if not math.isnan(correlation_coefficient) else O
        return correlations

    def underwriting_correlation(self):
        for field in fields(LoanSimulationResults):
            if field == WEIGHT_FIELD:
                continue
            self.risk_correlation[field.name] = self.calculate_correlation(field.name)

    def calculate_results(self):
        all_merchants = self.aggregate_results(self.all_merchants_simulation_results())
        portfolio_results = self.funded_merchants_simulation_results()
        portfolio_merchants_agg_results = self.aggregate_results(portfolio_results)
        sharpe = self.calculate_sharpe(portfolio_results)
        self.simulation_results = LenderSimulationResults(
            sharpe, all_merchants, portfolio_merchants_agg_results)
        self.underwriting_correlation()

    def all_merchants_simulation_results(self) -> List[LoanSimulationResults]:
        return [loan.simulation_results for loan in self.loans.values()]

    def funded_merchants_simulation_results(self) -> List[LoanSimulationResults]:
        return [loan.simulation_results for loan in self.funded_merchants_loans()]

    def funded_merchants_loans(self) -> List[LoanSimulation]:
        return [loan for loan in self.loans.values() if loan.ledger.total_credit() > 0]

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
