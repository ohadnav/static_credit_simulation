from copy import deepcopy
from dataclasses import fields
from unittest.mock import MagicMock

import numpy as np

from common import constants
from common.constants import LoanSimulationType
from common.numbers import O
from finance.lender import Lender, LenderSimulationResults, AggregatedLoanSimulationResults
from finance.loan_simulation import LoanSimulationResults, LoanSimulation
from simulation.merchant_factory import MerchantFactory
from tests.util_test import StatisticalTestCase


class TestLender(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestLender, self).setUp()
        self.data_generator.num_merchants = 10
        self.data_generator.max_num_products = 5
        self.merchants = self.factory.generate_merchants()
        self.lender = Lender(self.context, self.data_generator, self.merchants)

    def test_support_loan_types(self):
        self.data_generator.simulated_duration = self.data_generator.start_date + 1
        for loan_type in LoanSimulationType:
            self.context.loan_type = loan_type
            self.lender = Lender(self.context, self.data_generator, self.merchants)
            self.lender.simulate()
            self.assertEqual(type(self.lender.loans[self.merchants[0]]).__name__, loan_type.value)

    def test_loan_from_merchant(self):
        self.assertEqual(
            self.lender.loan_from_merchant(
                self.merchants[0], self.context, self.data_generator, self.context.loan_type).merchant,
            self.merchants[0])

    # noinspection PyTypeChecker
    def test_aggregate_results(self):
        self.assertEqual(
            Lender.aggregate_results(
                [
                    LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
                    LoanSimulationResults(3, 5, 5, 5, 5, 5, 5, 5, 5, 5)
                ]), AggregatedLoanSimulationResults(4, 4, 4, 4, 6, 6, 4, 4, 4))

    # noinspection PyTypeChecker
    def test_calculate_sharpe(self):
        results = [
            LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
            LoanSimulationResults(3, 5, 5, 5, 5, 5, 5, 5, 5, 5)
        ]
        std = np.std([1, 5])
        self.context.cost_of_capital = 3
        self.assertAlmostEqual(self.lender.calculate_sharpe(results), 1 / std)

    # noinspection PyTypeChecker
    def test_calculate_results(self):
        self.data_generator.simulated_duration = 1
        for merchant in self.merchants:
            self.lender.loans[merchant] = self.lender.loan_from_merchant(
                merchant, self.context, self.data_generator, self.context.loan_type)
            self.lender.loans[merchant].simulate()
            self.lender.loans[merchant].simulation_results.lender_profit = 1
        lsr_all = AggregatedLoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1)
        lsr_portfolio = AggregatedLoanSimulationResults(2, 2, 2, 2, 2, 2, 2, 2, 2)
        self.lender.aggregate_results = MagicMock(side_effect=[lsr_all, lsr_portfolio])
        self.lender.calculate_sharpe = MagicMock(return_value=5)
        self.lender.underwriting_correlation = MagicMock()
        self.lender.calculate_results()
        self.lender.underwriting_correlation.assert_called()
        self.assertEqual(
            self.lender.simulation_results,
            LenderSimulationResults(lsr_portfolio.lender_profit, 5, lsr_all, lsr_portfolio))

    # noinspection PyTypeChecker
    def test_calculate_correlation(self):
        merchants = self.factory.generate_merchants(num_merchants=2)
        loan1 = LoanSimulation(self.context, self.data_generator, merchants[0])
        loan1.simulation_results = LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
        loan1.total_credit = 1
        loan2 = LoanSimulation(self.context, self.data_generator, merchants[1])
        loan2.simulation_results = LoanSimulationResults(2, 2, 2, 2, 2, 2, 2, 2, 2, 2)
        loan2.total_credit = 1
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 2
            getattr(loan2.underwriting.initial_risk_context, risk_field).score = 2
        self.lender.loans = {1: loan1, 2: loan2}
        zero_map = {risk_field: 0 for risk_field in vars(self.context.risk_context).keys()}
        for field in fields(AggregatedLoanSimulationResults):
            self.assertDeepAlmostEqual(self.lender.calculate_correlation(field.name), zero_map)
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 1
        one_map = {risk_field: 1 for risk_field in vars(self.context.risk_context).keys()}
        for field in fields(AggregatedLoanSimulationResults):
            self.assertDeepAlmostEqual(self.lender.calculate_correlation(field.name), one_map)
        correlation = np.corrcoef([1, 2], [1.5, 2])[0][1]
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 1.5
        corr_map = {risk_field: correlation for risk_field in vars(self.context.risk_context).keys()}
        for field in fields(AggregatedLoanSimulationResults):
            self.assertDeepAlmostEqual(self.lender.calculate_correlation(field.name), corr_map)

    # noinspection PyTypeChecker
    def test_underwriting_correlation(self):
        merchants = self.factory.generate_merchants(num_merchants=2)
        loan1 = LoanSimulation(self.context, self.data_generator, merchants[0])
        loan1.simulation_results = LoanSimulationResults(1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
        loan1.total_credit = 1
        loan2 = LoanSimulation(self.context, self.data_generator, merchants[1])
        loan2.simulation_results = LoanSimulationResults(2, 2, 2, 2, 2, 2, 2, 2, 2, 2)
        loan2.total_credit = 1
        self.lender.loans = {1: loan1, 2: loan2}
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 1.5
            getattr(loan2.underwriting.initial_risk_context, risk_field).score = 2
        correlation = np.corrcoef([1, 2], [1.5, 2])[0][1]
        corr_map = {risk_field: correlation for risk_field in vars(self.context.risk_context).keys()}
        expected = {field.name: corr_map for field in fields(AggregatedLoanSimulationResults)}
        self.lender.underwriting_correlation()
        self.assertDeepAlmostEqual(self.lender.risk_correlation, expected)

    def test_simulation_results(self):
        self.data_generator.simulated_duration = constants.YEAR
        self.lender.simulate()
        for merchant in self.merchants:
            self.assertIsNotNone(self.lender.loans[merchant].simulation_results)
        self.assertIsNotNone(self.lender.simulation_results)
        zero_map = {risk_field: O for risk_field in vars(self.context.risk_context).keys()}
        not_expected = {field.name: zero_map for field in fields(AggregatedLoanSimulationResults)}
        try:
            self.assertFalse(self.lender.risk_correlation == not_expected)
        except AssertionError:
            self.setUp()
            self.lender.simulate()
            self.assertFalse(self.lender.risk_correlation == not_expected)

    def test_simulate_deterministic(self):
        self.data_generator.simulated_duration = constants.MONTH * 3
        self.data_generator.normal_ratio = MagicMock(return_value=1)
        self.data_generator.random = MagicMock(return_value=1)
        self.lender.simulate()
        self.data_generator.normal_ratio.assert_not_called()
        self.data_generator.random.assert_not_called()

    def test_generate_from_simulated_loans(self):
        factory = MerchantFactory(self.data_generator, self.context)
        merchants = factory.generate_merchants(num_merchants=5)
        lender1 = Lender(self.context, self.data_generator, merchants)
        lender1.simulate()
        loans = [LoanSimulation(self.context, self.data_generator, deepcopy(merchant)) for merchant in merchants]
        for loan in loans:
            loan.simulate()
        lender2 = Lender.generate_from_simulated_loans(loans)
        self.assertDeepAlmostEqual(lender1.simulation_results, lender2.simulation_results)
