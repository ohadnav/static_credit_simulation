import logging
import sys
from unittest import TestCase
from unittest.mock import MagicMock

import numpy as np
from autologging import traced, logged, TRACE

from common import constants
from common.constants import LoanType
from common.context import SimulationContext, DataGenerator
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

    def test_support_loan_types(self):
        self.data_generator.simulated_duration = constants.START_DATE + 1
        for loan_type in LoanType:
            self.context.loan_type = loan_type
            self.lender = Lender(self.context, self.data_generator, self.merchants)
            self.lender.simulate()
            self.assertEqual(type(self.lender.loans[self.merchants[0]]).__name__, loan_type.value)

    def test_loan_from_merchant(self):
        self.assertEqual(self.lender.loan_from_merchant(self.merchants[0]).merchant, self.merchants[0])

    def test_aggregate_results(self):
        self.assertEqual(
            Lender.aggregate_results(
                [
                    LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1),
                    LoanSimulationResults(3, 5, 5, 5, 5, 5, 5, 5, 5)
                ]), AggregatedLoanSimulationResults(4, 4, 4, 4, 6, 4, 4, 4))

    def test_calculate_sharpe(self):
        results = [
            LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1),
            LoanSimulationResults(3, 5, 5, 5, 5, 5, 5, 5, 5)
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
        lsr_all = AggregatedLoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1)
        lsr_portfolio = AggregatedLoanSimulationResults(2, 2, 2, 2, 2, 2, 2, 2)
        self.lender.aggregate_results = MagicMock(side_effect=[lsr_all, lsr_portfolio])
        self.lender.calculate_sharpe = MagicMock(return_value=5)
        self.lender.calculate_results()
        self.assertEqual(
            self.lender.simulation_results,
            LenderSimulationResults(lsr_portfolio.lender_profit, 5, lsr_all, lsr_portfolio))

    def test_simulate(self):
        self.data_generator.normal_ratio = MagicMock(return_value=1)
        self.data_generator.random = MagicMock(return_value=1)
        self.lender.simulate()
        self.assertIsNotNone(self.lender.simulation_results)
        for merchant in self.merchants:
            self.assertIsNotNone(self.lender.loans[merchant].simulation_results)
        self.data_generator.normal_ratio.assert_not_called()
