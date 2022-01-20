from copy import deepcopy
from dataclasses import fields
from unittest.mock import MagicMock

import numpy as np

from common import constants
from common.enum import LoanSimulationType, LoanReferenceType
from common.numbers import O, ONE, Float, Percent, Int, TWO
from finance.lender import Lender, LenderSimulationResults, AggregatedLoanSimulationResults, WEIGHT_FIELD
from finance.loan_simulation import LoanSimulationResults, LoanSimulation
from simulation.merchant_factory import MerchantFactory
from statistical_tests.statistical_util import StatisticalTestCase


class TestLender(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestLender, self).setUp()
        self.data_generator.num_merchants = 10
        self.data_generator.max_num_products = 5
        self.merchants = self.factory.generate_merchants()
        self.lender = Lender(self.context, self.data_generator, self.merchants)

    def test_support_loan_types(self):
        self.data_generator.num_merchants = 2
        self.data_generator.simulated_duration = self.data_generator.start_date + 1
        for loan_type in LoanSimulationType:
            self.lender = Lender(self.context, self.data_generator, self.merchants, loan_type)
            self.lender.simulate()
            self.assertEqual(type(self.lender.loans[self.merchants[0]]).__name__, loan_type.value)

    def test_loan_from_merchant(self):
        self.assertEqual(self.lender.generate_loan_from_merchant(self.merchants[0]).merchant, self.merchants[0])

    def test_aggregate_results(self):
        self.lender.merchants = [self.merchants[0]] * 3
        three = Float(3)
        five = Float(5)
        four = Float(4)
        six = Float(6)
        self.assertEqual(
            self.lender.aggregate_results(
                [
                    LoanSimulationResults(ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, Int(1)),
                    LoanSimulationResults(
                        three, five, five, five, five, five, five, five, five, five, five, five, Int(5))
                ]),
            AggregatedLoanSimulationResults(
                four, four, four, four, six, six, four, six, four, four, three, Percent(2 / 3), Int(2), four))

    def test_calculate_sharpe(self):
        five = Float(5)
        three = Float(3)
        results = [
            LoanSimulationResults(ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, Int(1)),
            LoanSimulationResults(three, five, five, five, five, five, five, five, five, five, five, five, Int(3))
        ]
        std = np.std([ONE, five])
        self.context.cost_of_capital = three
        self.assertEqual(self.lender.calculate_sharpe(results), ONE / std)

    def test_calculate_results(self):
        self.data_generator.simulated_duration = 1
        for merchant in self.merchants:
            self.lender.loans[merchant] = self.lender.simulate_merchant(merchant)
        self.lender.underwriting_correlation = MagicMock()
        self.lender.calculate_results()
        self.lender.underwriting_correlation.assert_called()
        self.assertDeepAlmostEqual(
            self.lender.simulation_results,
            LenderSimulationResults(
                self.lender.calculate_sharpe(self.lender.funded_merchants_simulation_results()),
                self.lender.aggregate_results(self.lender.all_merchants_simulation_results()),
                self.lender.aggregate_results(self.lender.funded_merchants_simulation_results())))

    def test_calculate_correlation(self):
        merchants = self.factory.generate_merchants(num_merchants=2)
        loan1 = LoanSimulation(self.context, self.data_generator, merchants[0])
        loan1.simulation_results = LoanSimulationResults(
            ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, Int(1))
        loan1.ledger.total_credit = 1
        loan2 = LoanSimulation(self.context, self.data_generator, merchants[1])
        loan2.simulation_results = LoanSimulationResults(
            TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, Int(2))
        loan2.ledger.total_credit = 1
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 2
            getattr(loan2.underwriting.initial_risk_context, risk_field).score = 2
        self.lender.loans = {1: loan1, 2: loan2}
        zero_map = {risk_field: 0 for risk_field in vars(self.context.risk_context).keys()}
        self.assert_correlation_map_equal(zero_map)
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 1
        one_map = {risk_field: 1 for risk_field in vars(self.context.risk_context).keys()}
        self.assert_correlation_map_equal(one_map)
        correlation = np.corrcoef([1, 2], [1.5, 2])[0][1]
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 1.5
        corr_map = {risk_field: correlation for risk_field in vars(self.context.risk_context).keys()}
        self.assert_correlation_map_equal(corr_map)

    def assert_correlation_map_equal(self, expected_map):
        for field in fields(LoanSimulationResults):
            if field == WEIGHT_FIELD:
                continue
            self.assertDeepAlmostEqual(self.lender.calculate_correlation(field.name), expected_map)

    def test_underwriting_correlation(self):
        merchants = self.factory.generate_merchants(num_merchants=2)
        loan1 = LoanSimulation(self.context, self.data_generator, merchants[0])
        loan1.simulation_results = LoanSimulationResults(
            ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, ONE, Int(1))
        loan1.ledger.total_credit = 1
        loan2 = LoanSimulation(self.context, self.data_generator, merchants[1])
        loan2.simulation_results = LoanSimulationResults(
            TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, TWO, Int(2))
        loan2.ledger.total_credit = 1
        self.lender.loans = {1: loan1, 2: loan2}
        for risk_field in vars(self.context.risk_context).keys():
            getattr(loan1.underwriting.initial_risk_context, risk_field).score = 1.5
            getattr(loan2.underwriting.initial_risk_context, risk_field).score = 2
        correlation = np.corrcoef([1, 2], [1.5, 2])[0][1]
        corr_map = {risk_field: correlation for risk_field in vars(self.context.risk_context).keys()}
        expected = {field.name: corr_map for field in fields(LoanSimulationResults) if field != WEIGHT_FIELD}
        self.lender.underwriting_correlation()
        self.assertDeepAlmostEqual(self.lender.risk_correlation, expected)

    def test_simulation_results(self):
        self.data_generator.simulated_duration = constants.YEAR
        self.lender.simulate()
        for merchant in self.merchants:
            self.assertIsNotNone(self.lender.loans[merchant].simulation_results)
        self.assertIsNotNone(self.lender.simulation_results)
        self.assertEqual(self.lender.simulation_results.all.num_merchants, len(self.merchants))
        self.assertEqual(self.lender.simulation_results.funded.num_merchants, len(self.lender.funded_merchants_loans()))
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
        self.data_generator.simulated_duration = constants.YEAR
        factory = MerchantFactory(self.data_generator, self.context)
        merchants = factory.generate_merchants(num_merchants=5)
        lender1 = Lender(self.context, self.data_generator, merchants)
        lender1.simulate()
        loans = [LoanSimulation(self.context, self.data_generator, deepcopy(merchant)) for merchant in merchants]
        for loan in loans:
            loan.simulate()
        lender2 = Lender.generate_from_simulated_loans(loans)
        self.assertDeepAlmostEqual(lender1.simulation_results, lender2.simulation_results)

    def test_generate_from_reference_loans(self):
        self.context.loan_reference_type = LoanReferenceType.REVENUE_CAGR
        self.data_generator.simulated_duration = constants.YEAR
        self.merchants = self.merchants[:2]
        reference_loans = [
            Lender.generate_loan(merchant, self.context, self.data_generator, LoanSimulationType.DEFAULT, None) for
            merchant in self.merchants]
        self.lender = Lender.generate_from_reference_loans(reference_loans)
        self.assertDeepAlmostEqual(self.lender.merchants, self.merchants)
        self.assertDeepAlmostEqual(list(self.lender.reference_loans.values()), reference_loans)
        self.lender.simulate()
        actual_reference_loans = [loan.reference_loan for loan in self.lender.loans.values()]
        self.assertDeepAlmostEqual(actual_reference_loans, reference_loans)
