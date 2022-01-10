import logging
import sys
from copy import deepcopy
from typing import List, Tuple, Any
from unittest import TestCase

from common.constants import LoanType
from common.context import SimulationContext, DataGenerator
from finance.lender import Lender
from finance.line_of_credit import DynamicLineOfCredit, LineOfCredit
from finance.loan import Loan
from seller.merchant import Merchant
from statistical_tests.statistical_test import statistical_test_bool


class TestStatisticalFinance(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=logging.INFO if sys.gettrace() else logging.WARNING, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.context = SimulationContext()

    @statistical_test_bool(confidence=0.6, num_lists=4)
    def test_line_of_credit_more_efficient(self, is_true: List[List[Tuple[bool, Any]]]):
        line_of_credit = None
        regular_loan = None
        diff = False
        while not diff:
            merchant = Merchant.generate_simulated(self.data_generator)
            regular_loan = Loan(self.context, self.data_generator, deepcopy(merchant))
            line_of_credit = LineOfCredit(self.context, self.data_generator, merchant)
            line_of_credit.simulate()
            if line_of_credit.total_debt > 0:
                regular_loan.simulate()
                diff = line_of_credit.simulation_results != regular_loan.simulation_results
        is_true[0].append(
            (
                line_of_credit.simulation_results.valuation_cagr >
                regular_loan.simulation_results.valuation_cagr,
                (round(
                    line_of_credit.simulation_results.valuation_cagr -
                    regular_loan.simulation_results.valuation_cagr,
                    2), line_of_credit, regular_loan)))
        is_true[1].append(
            (
                line_of_credit.total_debt > regular_loan.total_debt,
                (round(
                    line_of_credit.total_debt - regular_loan.total_debt,
                    2), line_of_credit, regular_loan)))
        is_true[2].append(
            (
                line_of_credit.average_apr() < regular_loan.average_apr(),
                (round(
                    line_of_credit.average_apr() - regular_loan.average_apr(),
                    2), line_of_credit, regular_loan)))
        is_true[3].append(
            (
                line_of_credit.simulation_results.lender_profit > regular_loan.simulation_results.lender_profit,
                (round(
                    line_of_credit.simulation_results.lender_profit - regular_loan.simulation_results.lender_profit,
                    2), line_of_credit, regular_loan)))

    @statistical_test_bool(confidence=0.6, num_lists=5, times=10)
    def test_dynamic_line_of_credit_superior(self, is_true: List[List[Tuple[bool, Any]]]):
        dynamic_context = SimulationContext(LoanType.DYNAMIC_LINE_OF_CREDIT)
        dynamic_context.merchant_cost_of_acquisition = 0
        regular_context = SimulationContext(LoanType.FLAT_FEE)
        regular_context.merchant_cost_of_acquisition = 0
        merchants = []
        num_merchants = 20
        while len(merchants) < num_merchants:
            merchant = Merchant.generate_simulated(self.data_generator)
            regular_loan = Loan(self.context, self.data_generator, deepcopy(merchant))
            dloc = DynamicLineOfCredit(self.context, self.data_generator, merchant)
            dloc.simulate()
            regular_loan.simulate()
            diff = dloc.simulation_results != regular_loan.simulation_results
            if dloc.total_debt > 0:
                if diff:
                    merchants.append(merchant)
        regular_lender = Lender(regular_context, self.data_generator, merchants)
        dynamic_lender = Lender(dynamic_context, self.data_generator, deepcopy(merchants))
        regular_lender.simulate()
        dynamic_lender.simulate()
        self.assertNotEqual(regular_lender.simulation_results, dynamic_lender.simulation_results)
        is_true[0].append(
            (regular_lender.simulation_results.lender_gross_profit <
             dynamic_lender.simulation_results.lender_gross_profit, (regular_lender, dynamic_lender)))
        is_true[1].append(
            (regular_lender.simulation_results.portfolio_merchants.valuation_cagr <
             dynamic_lender.simulation_results.portfolio_merchants.valuation_cagr, (regular_lender, dynamic_lender)))
        is_true[2].append(
            (regular_lender.simulation_results.portfolio_merchants.bankruptcy_rate >
             dynamic_lender.simulation_results.portfolio_merchants.bankruptcy_rate, (regular_lender, dynamic_lender)))
        is_true[3].append(
            (regular_lender.simulation_results.portfolio_merchants.net_cashflow_cagr <
             dynamic_lender.simulation_results.portfolio_merchants.net_cashflow_cagr, (regular_lender, dynamic_lender)))
        is_true[4].append(
            (regular_lender.simulation_results.portfolio_merchants.revenues_cagr <
             dynamic_lender.simulation_results.portfolio_merchants.revenues_cagr, (regular_lender, dynamic_lender)))
