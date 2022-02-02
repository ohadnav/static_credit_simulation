from copy import deepcopy
from dataclasses import fields
from unittest.mock import MagicMock

import numpy as np

from common import constants
from common.local_enum import LoanSimulationType
from common.local_numbers import O, ONE, Float, Percent, Int, ONE_INT, Duration, Date, TWO, Dollar
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation
from finance.loan_simulation_results import LoanSimulationResults
from loan_simulation_results import ONE_LSR, TWO_LSR, WEIGHT_FIELD, AggregatedLoanSimulationResults
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
        six = Float(6)
        weighted_avg = Float((5 * 5 + 1) / (1 + 5))
        loan_lsrs = [ONE_LSR, LoanSimulationResults.generate_from_float(five)]
        expected = AggregatedLoanSimulationResults.generate_from_numbers(
            weighted_avg, six, three, Int(2), Percent(2 / 3))
        self.assertEqual(self.lender.aggregate_results(loan_lsrs), expected)

    def test_calculate_results(self):
        self.data_generator.simulated_duration = ONE_INT
        self.lender.all_merchants_simulation_results = MagicMock(return_value=[ONE_LSR])
        self.lender.funded_merchants_simulation_results = MagicMock(return_value=[ONE_LSR])
        self.lender.underwriting_correlation = MagicMock()
        self.lender.reference = None
        self.lender.calculate_results()
        self.lender.underwriting_correlation.assert_called()
        self.assertIsNotNone(self.lender.simulation_results)

    def test_calculate_correlation(self):
        merchants = self.factory.generate_merchants(num_merchants=2)
        loan1 = LoanSimulation(self.context, self.data_generator, merchants[0])
        loan1.simulation_results = ONE_LSR
        loan1.ledger.total_credit = MagicMock(return_value=1)
        loan2 = LoanSimulation(self.context, self.data_generator, merchants[1])
        loan2.simulation_results = TWO_LSR
        loan2.ledger.total_credit = MagicMock(return_value=1)
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
        loan1.simulation_results = ONE_LSR
        loan1.ledger.total_credit = MagicMock(return_value=1)
        loan2 = LoanSimulation(self.context, self.data_generator, merchants[1])
        loan2.simulation_results = TWO_LSR
        loan2.ledger.total_credit = MagicMock(return_value=1)
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
        self.data_generator.simulated_duration = Duration(constants.YEAR)
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
        self.data_generator.simulated_duration = Duration(constants.YEAR)
        self.data_generator.normal_ratio = MagicMock(return_value=1)
        self.data_generator.random = MagicMock(return_value=1)
        self.lender.simulate()
        self.data_generator.normal_ratio.assert_not_called()
        self.data_generator.random.assert_not_called()

    def test_generate_from_simulated_loans(self):
        self.data_generator.simulated_duration = Duration(constants.YEAR)
        factory = MerchantFactory(self.data_generator, self.context)
        merchants = factory.generate_merchants(num_merchants=5)
        lender1 = Lender(self.context, self.data_generator, merchants)
        lender1.simulate()
        loans = [LoanSimulation(self.context, self.data_generator, deepcopy(merchant)) for merchant in merchants]
        for loan in loans:
            loan.simulate()
        lender2 = Lender.generate_from_simulated_loans(loans)
        self.assertDeepAlmostEqual(lender1.simulation_results, lender2.simulation_results)

    def test_prepare_snapshots(self):
        self.context.snapshot_cycle = constants.MONTH
        three = Float(3)
        five = Float(5)
        weighted_avg = Float((5 * 5 + 1) / (1 + 5))
        six = Float(6)
        self.lender.merchants = self.lender.merchants[:2]
        loan1 = LoanSimulation(self.context, self.data_generator, self.merchants[0])
        loan1.simulation_results = ONE_LSR
        loan1.snapshots = {Date(day): loan1.simulation_results for day in self.lender.snapshot_dates()}
        loan2 = LoanSimulation(self.context, self.data_generator, self.merchants[1])
        loan2.simulation_results = LoanSimulationResults.generate_from_float(five)
        loan2.snapshots = {Date(day): loan2.simulation_results for day in self.lender.snapshot_dates()}
        self.lender.loans = {self.lender.merchants[0]: loan1, self.lender.merchants[1]: loan2}
        expected = AggregatedLoanSimulationResults.generate_from_numbers(weighted_avg, six, three, Int(2), ONE)
        expected_snapshots = {Date(day): expected for day in self.lender.snapshot_dates()}
        self.lender.prepare_snapshots()
        self.assertDeepAlmostEqual(self.lender.snapshots, expected_snapshots)

    def test_get_snapshots_for_day(self):
        self.context.snapshot_cycle = constants.MONTH
        self.lender.merchants = self.lender.merchants[:2]
        loan1 = LoanSimulation(self.context, self.data_generator, self.merchants[0])
        loan1.snapshots = {Date(day): ONE_LSR for day in self.lender.snapshot_dates()}
        loan2 = LoanSimulation(self.context, self.data_generator, self.merchants[1])
        loan2.snapshots = {self.context.snapshot_cycle: TWO_LSR}
        loan2.today = self.context.snapshot_cycle
        self.lender.loans = {self.lender.merchants[0]: loan1, self.lender.merchants[1]: loan2}
        self.assertDeepAlmostEqual(self.lender.get_snapshots_for_day(self.context.snapshot_cycle), [ONE_LSR, TWO_LSR])
        self.assertDeepAlmostEqual(
            self.lender.get_snapshots_for_day(self.context.snapshot_cycle * 2), [ONE_LSR, TWO_LSR])

    def test_risk_order_counts(self):
        loans = [LoanSimulation(self.context, self.data_generator, self.merchants[i]) for i in range(2)]
        for i in range(2):
            loans[i].simulation_results = LoanSimulationResults.generate_from_float(ONE)
            loans[i].ledger.total_credit = MagicMock(return_value=ONE)
        self.lender.merchants = self.merchants[:2]
        self.lender.loans = {self.merchants[i]: loans[i] for i in range(2)}
        lender2 = deepcopy(self.lender)
        lender2.reference = self.lender
        self.assertEqual(lender2.risk_order_counts(), [0, 0, 2, 0, 0])
        self.lender.loans[self.merchants[0]].ledger.total_credit = MagicMock(return_value=O)
        self.assertEqual(lender2.risk_order_counts(), [0, 0, 1, 0, 0])

    def test_lender_profit_per_risk_order(self):
        loans = [LoanSimulation(self.context, self.data_generator, self.merchants[i]) for i in range(2)]
        for i in range(2):
            loans[i].simulation_results = LoanSimulationResults.generate_from_float(ONE)
            loans[i].ledger.total_credit = MagicMock(return_value=ONE)
        self.lender.loans = {self.merchants[i]: loans[i] for i in range(2)}
        self.assertEqual(self.lender.lender_profit_per_risk_order()[self.lender.risk_order.get_order(ONE)], ONE)
        loans[0].simulation_results.lender_profit = TWO
        self.assertEqual(self.lender.lender_profit_per_risk_order()[self.lender.risk_order.get_order(ONE)], Dollar(1.5))
