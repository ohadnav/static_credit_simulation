import logging
import sys
from typing import List, Union, Tuple, Any
from unittest import TestCase
from unittest.mock import MagicMock

import numpy as np
from autologging import traced, logged, TRACE

from common.context import SimulationContext, DataGenerator
from common.statistical_test import statistical_test_bool
from finance.lender import Lender, LenderSimulationResults, AggregatedLoanSimulationResults
from finance.loan import LoanSimulationResults
from seller.merchant import Merchant


@traced
@logged
class TestLender(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=TRACE if sys.gettrace() else logging.WARNING, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.context = SimulationContext()
        self.data_generator.num_merchants = 2
        self.data_generator.max_num_products = 2
        self.data_generator.num_products = min(self.data_generator.num_products, self.data_generator.max_num_products)
        self.merchants = [Merchant.generate_simulated(self.data_generator) for _ in
                          range(self.data_generator.num_merchants)]
        self.lender = Lender(self.context, self.data_generator, self.merchants)

    def test_loan_from_merchant(self):
        self.assertEqual(self.lender.loan_from_merchant(self.merchants[0]).merchant, self.merchants[0])

    def test_aggregate_results(self):
        self.assertEqual(
            Lender.aggregate_results(
                [
                    LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, True),
                    LoanSimulationResults(3, 5, 5, 5, 5, 5, 5, 5, False)
                ]), AggregatedLoanSimulationResults(4, 4, 4, 4, 6, 4, 4, 0.5))

    def test_calculate_sharpe(self):
        results = [
            LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, True),
            LoanSimulationResults(3, 5, 5, 5, 5, 5, 5, 5, False)
        ]
        std = np.std([1, 5])
        self.context.cost_of_capital = 3
        self.assertAlmostEqual(self.lender.calculate_sharpe(results), 1 / std)

    def test_calculate_results(self):
        self.data_generator.simulated_duration = 1
        for merchant in self.merchants:
            self.lender.loans[merchant] = self.lender.loan_from_merchant(merchant)
            self.lender.loans[merchant].simulate()
            self.lender.loans[merchant].simulation_results.lender_profit = 1
        lsr_all = AggregatedLoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 0.2)
        lsr_portfolio = AggregatedLoanSimulationResults(2, 2, 2, 2, 2, 2, 2, 0.5)
        self.lender.aggregate_results = MagicMock(side_effect=[lsr_all, lsr_portfolio])
        self.lender.calculate_sharpe = MagicMock(return_value=5)
        self.lender.calculate_results()
        self.assertEqual(
            self.lender.simulation_results,
            LenderSimulationResults(lsr_portfolio.lender_profit, 5, lsr_all, lsr_portfolio))

    def test_simulate(self):
        self.data_generator.simulated_duration = 10
        self.lender.simulate()
        self.assertIsNotNone(self.lender.simulation_results)
        for merchant in self.merchants:
            self.assertIsNotNone(self.lender.loans[merchant].simulation_results)

    @statistical_test_bool(num_lists=5, times=5, confidence=0.8)
    def test_lending_helps_and_profitable(self, is_true: List[List[Union[bool, Tuple[bool, Any]]]]):
        self.data_generator.num_merchants = 100
        self.data_generator.num_products = 5
        self.merchants = [Merchant.generate_simulated(self.data_generator) for _ in
                          range(self.data_generator.num_merchants)]
        self.lender = Lender(self.context, self.data_generator, self.merchants)
        self.lender.simulate()
        is_true[0].append(self.lender.simulation_results.lender_gross_profit > 0)
        is_true[1].append(
            self.lender.simulation_results.portfolio_merchants.valuation_cagr > self.lender.simulation_results.all_merchants.valuation_cagr)
        is_true[2].append(
            self.lender.simulation_results.portfolio_merchants.revenues_cagr > self.lender.simulation_results.all_merchants.revenues_cagr)
        is_true[3].append(
            self.lender.simulation_results.portfolio_merchants.net_cashflow_cagr > self.lender.simulation_results.all_merchants.net_cashflow_cagr)
        is_true[4].append(
            self.lender.simulation_results.portfolio_merchants.bankruptcy_rate < self.lender.simulation_results.all_merchants.bankruptcy_rate)
