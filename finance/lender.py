from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import fields
from typing import List, MutableMapping, Optional, Mapping

import numpy as np
from joblib import delayed

from common.context import SimulationContext, DataGenerator
from common.local_enum import LoanSimulationType
from common.local_numbers import Percent, O, Int, Date, Dollar, FloatRange, Float
from common.primitive import Primitive
from common.tqdm_parallel import TqdmParallel
from common.util import get_key_from_value, intersection
from finance.line_of_credit import LineOfCreditSimulation, DynamicLineOfCreditSimulation, InvoiceFinancingSimulation
from finance.loan_simulation import LoanSimulation
from finance.loan_simulation_results import LoanSimulationResults
from finance.risk_order import RiskOrder
from lender_simulation_results import LenderSimulationResults
from loan_simulation_childs import IncreasingRebateLoanSimulation, NoCapitalLoanSimulation
from loan_simulation_results import O_LSR, WEIGHT_FIELD, AggregatedLoanSimulationResults
from seller.merchant import Merchant

LOAN_TYPES_MAPPING = {
    LoanSimulationType.INCREASING_REBATE: IncreasingRebateLoanSimulation,
    LoanSimulationType.DYNAMIC_LINE_OF_CREDIT: DynamicLineOfCreditSimulation,
    LoanSimulationType.LINE_OF_CREDIT: LineOfCreditSimulation,
    LoanSimulationType.NO_CAPITAL: NoCapitalLoanSimulation,
    LoanSimulationType.DEFAULT: LoanSimulation,
    LoanSimulationType.INVOICE_FINANCING: InvoiceFinancingSimulation
}


class Lender(Primitive):
    def __init__(
            self, context: SimulationContext, data_generator: DataGenerator, merchants: List[Merchant],
            loan_type: LoanSimulationType = LoanSimulationType.DEFAULT,
            reference_lender: Optional[Lender] = None):
        super(Lender, self).__init__(data_generator)
        self.merchants = merchants
        self.context = context
        self.simulation_results: Optional[LenderSimulationResults] = None
        self.loans: MutableMapping[Merchant, LoanSimulation] = {}
        self.risk_correlation: MutableMapping[str, MutableMapping[str, Percent]] = {}
        self.loan_type = loan_type
        self.reference = reference_lender
        self.risk_order = RiskOrder()
        self.snapshots: MutableMapping[Date, AggregatedLoanSimulationResults] = {}

    @classmethod
    def generate_from_simulated_loans(cls, loans: List[LoanSimulation], reference: Optional[Lender] = None) -> Lender:
        merchants = [loan.merchant for loan in loans]
        context = deepcopy(loans[0].context)
        loan_type = get_key_from_value(type(loans[0]), LOAN_TYPES_MAPPING)
        data_generator = loans[0].data_generator
        lender = Lender(context, data_generator, merchants, loan_type, reference)
        lender.loans = {loan.merchant: loan for loan in loans}
        lender.calculate_results()
        return lender

    @staticmethod
    def generate_loan(
            merchant: Merchant, context: SimulationContext, data_generator: DataGenerator,
            loan_type: LoanSimulationType, reference_loan: Optional[LoanSimulation]) -> LoanSimulation:
        return LOAN_TYPES_MAPPING[loan_type](context, data_generator, merchant, reference_loan)

    def set_reference(self, reference: Lender):
        self.reference = reference
        self.risk_order = reference.risk_order

    def get_risk_order(self, merchant: Merchant) -> Int:
        revenue_cagr = self.loans[merchant].revenue_cagr()
        merchant_top_line = merchant.annual_top_line(self.loans[merchant].today)
        order = self.risk_order.get_order(revenue_cagr)
        if merchant_top_line < self.context.min_merchant_top_line:
            order = self.risk_order.prev_order(order)
        if merchant_top_line > self.context.max_merchant_top_line:
            order = self.risk_order.next_order(order)
        return order

    def lsr_or_zero(self, merchant: Merchant) -> LoanSimulationResults:
        if self.loans[merchant].ledger.total_credit():
            return self.loans[merchant].simulation_results
        return O_LSR

    def agg_compare(self, lender: Optional[Lender] = None) -> AggregatedLoanSimulationResults:
        lender = lender or self.reference
        diff_lsr = [self.lsr_or_zero(merchant) - lender.lsr_or_zero(merchant) for merchant in self.merchants]
        return self.aggregate_results(diff_lsr)

    def risk_order_counts(self) -> List[Int]:
        if not self.reference:
            return self.get_risk_order_counts_for_list(self.funded_merchants_simulation_results())
        funded_by_both = self.funded_also_by_reference_lender()
        lsr_of_these_merchants = [self.loans[merchant].simulation_results for merchant in funded_by_both]
        return self.get_risk_order_counts_for_list(lsr_of_these_merchants)

    def funded_also_by_reference_lender(self) -> List[Merchant]:
        funded_by_self = [loan.merchant for loan in self.funded_merchants_loans()]
        if not self.reference:
            return funded_by_self
        funded_by_reference = [loan.merchant for loan in self.reference.funded_merchants_loans()]
        funded_by_both = intersection(funded_by_self, funded_by_reference)
        return funded_by_both

    def lender_profit_per_risk_order(self) -> List[Dollar]:
        order_to_loans: Mapping[FloatRange: List[LoanSimulation]] = {
            order: [self.loans[merchant] for merchant in self.funded_also_by_reference_lender() if
                self.risk_order.get_order_range(self.loans[merchant].simulation_results.revenue_cagr) == order] for
            order in
            self.risk_order.risk_orders}
        return [Float.mean([loan.simulation_results.lender_profit for loan in loans]) for order, loans in
            order_to_loans.items()]

    def get_risk_order_counts_for_list(self, lsr_list: List[LoanSimulationResults]) -> List[Int]:
        return self.risk_order.count_per_order([lsr.revenue_cagr for lsr in lsr_list])

    def generate_loan_from_merchant(self, merchant: Merchant) -> LoanSimulation:
        reference_loan = self.reference.loans[merchant] if self.reference else None
        return Lender.generate_loan(merchant, self.context, self.data_generator, self.loan_type, reference_loan)

    def aggregate_results(self, simulations_results: List[LoanSimulationResults]) -> AggregatedLoanSimulationResults:
        return AggregatedLoanSimulationResults.generate_from_list(simulations_results, len(self.merchants))

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
        self.simulation_results = LenderSimulationResults(all_merchants, portfolio_merchants_agg_results)
        self.underwriting_correlation()
        if self.reference:
            self.risk_order = self.reference.risk_order
        # else:
        #     self.risk_order = RiskOrder([lsr.revenue_cagr for lsr in portfolio_results])
        self.prepare_snapshots()

    def snapshot_dates(self) -> List[Date]:
        return [Date(day) for day in
            range(self.context.snapshot_cycle, self.data_generator.simulated_duration, self.context.snapshot_cycle)]

    def prepare_snapshots(self):
        if not self.context.snapshot_cycle:
            return
        for day in self.snapshot_dates():
            day_snapshots = self.get_snapshots_for_day(day)
            self.snapshots[day] = self.aggregate_results(day_snapshots)

    def get_snapshots_for_day(self, day: Date) -> List[LoanSimulationResults]:
        day_snapshots = []
        for loan in self.loans.values():
            if day in loan.snapshots:
                day_snapshots.append(loan.snapshots[day])
            elif day > loan.today and loan.snapshots:
                day_snapshots.append(loan.snapshots[list(loan.snapshots)[-1]])
        return day_snapshots

    def all_merchants_simulation_results(self) -> List[LoanSimulationResults]:
        return [loan.simulation_results for loan in self.loans.values()]

    def funded_merchants_simulation_results(self) -> List[LoanSimulationResults]:
        return [loan.simulation_results for loan in self.funded_merchants_loans()]

    def funded_merchants_loans(self) -> List[LoanSimulation]:
        return [loan for loan in self.loans.values() if loan.ledger.total_credit() > O]

    def simulate(self):
        if self.simulation_results:
            return
        simulated_loans = TqdmParallel(desc=f'{self.id}({self.loan_type.value})', total=len(self.merchants))(
            delayed(self.simulate_merchant)(merchant) for merchant in self.merchants)
        for loan in simulated_loans:
            self.loans[loan.merchant] = loan
        self.calculate_results()

    def simulate_merchant(self, merchant: Merchant) -> LoanSimulation:
        loan = self.generate_loan_from_merchant(merchant)
        loan.simulate()
        return loan
