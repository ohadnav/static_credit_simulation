from unittest.mock import MagicMock

from common import constants
from common.enum import LoanSimulationType
from common.numbers import Dollar
from finance.line_of_credit import DynamicLineOfCreditSimulation, LineOfCreditSimulation
from seller.merchant import Merchant
from tests.util_test import BaseTestCase


class TestLineOfCredit(BaseTestCase):
    def setUp(self) -> None:
        super(TestLineOfCredit, self).setUp()
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.line_of_credit = LineOfCreditSimulation(self.context, self.data_generator, self.merchant)
        self.line_of_credit.underwriting.approved = MagicMock(return_value=True)

    def test_apr_non_concurrent_loan(self):
        self.line_of_credit.approved_amount = MagicMock(return_value=10)
        self.line_of_credit.credit_needed = MagicMock(return_value=5)
        self.line_of_credit.update_credit()
        self.assertAlmostEqual(self.line_of_credit.debt_to_loan_amount(self.line_of_credit.outstanding_balance()), 5)
        self.assertAlmostEqual(
            self.line_of_credit.average_apr(), self.line_of_credit.calculate_apr(self.context.loan_duration))

    def test_apr_concurrent_loan(self):
        self.line_of_credit.approved_amount = MagicMock(return_value=3)
        self.line_of_credit.credit_needed = MagicMock(return_value=2)
        self.line_of_credit.default_repayment_rate = MagicMock(return_value=0.3)
        half_duration = self.context.loan_duration / 2
        apr1 = self.line_of_credit.calculate_apr(half_duration)
        apr2 = self.line_of_credit.calculate_apr(half_duration * 2)
        self.line_of_credit.update_credit()
        self.assertAlmostEqual(self.line_of_credit.average_apr(), apr2)
        self.line_of_credit.today += half_duration - 1
        self.line_of_credit.repay_loans(self.line_of_credit.outstanding_balance())
        self.assertAlmostEqual(self.line_of_credit.average_apr(), apr1)
        self.line_of_credit.credit_needed = MagicMock(return_value=1)
        self.line_of_credit.update_credit()
        self.assertAlmostEqual(self.line_of_credit.average_apr(), (apr1 * 2 + apr2) / 3)

    def test_remaining_credit(self):
        self.line_of_credit.approved_amount = MagicMock(return_value=self.line_of_credit.loan_amount())
        self.assertEqual(self.line_of_credit.remaining_credit(), self.line_of_credit.loan_amount())
        self.line_of_credit.add_debt(Dollar(1))
        self.assertEqual(self.line_of_credit.remaining_credit(), self.line_of_credit.loan_amount() - 1)

    def test_update_credit(self):
        self.line_of_credit.credit_needed = MagicMock(return_value=0)
        self.line_of_credit.update_credit()
        self.assertEqual(self.line_of_credit.outstanding_balance(), 0)
        self.line_of_credit.credit_needed = MagicMock(return_value=1)
        prev_cash = self.line_of_credit.current_cash
        self.line_of_credit.update_credit()
        self.assertAlmostEqual(self.line_of_credit.current_cash, prev_cash + 1)
        self.line_of_credit.remaining_credit = MagicMock(return_value=0)
        self.line_of_credit.update_credit()
        self.assertEqual(self.line_of_credit.current_cash, prev_cash + 1)


class TestDynamicLineOfCredit(BaseTestCase):
    def setUp(self) -> None:
        super(TestDynamicLineOfCredit, self).setUp()
        self.context.loan_type = LoanSimulationType.DYNAMIC_LINE_OF_CREDIT
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.dynamic_line_of_credit = DynamicLineOfCreditSimulation(self.context, self.data_generator, self.merchant)
        self.dynamic_line_of_credit.underwriting.approved = MagicMock(return_value=True)

    def test_revenue_collateralization(self):
        self.context.revenue_collateralization = False
        self.dynamic_line_of_credit.underwriting.approved = MagicMock(return_value=False)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertEqual(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())
        self.context.revenue_collateralization = True
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertEqual(
            self.dynamic_line_of_credit.current_repayment_rate, constants.MAX_REPAYMENT_RATE)

    def test_update_credit(self):
        self.dynamic_line_of_credit.update_repayment_rate = MagicMock()
        self.dynamic_line_of_credit.update_credit()
        self.dynamic_line_of_credit.update_repayment_rate.assert_called()

    def test_repayment_rate_unchaged(self):
        self.dynamic_line_of_credit.underwriting.aggregated_score = MagicMock(
            return_value=self.context.agg_score_benchmark)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertEqual(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())

    def test_repayment_rate_increase(self):
        self.dynamic_line_of_credit.underwriting.aggregated_score = MagicMock(
            return_value=self.context.agg_score_benchmark * 0.9)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertGreater(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())

    def test_repayment_rate_decrease(self):
        self.dynamic_line_of_credit.underwriting.aggregated_score = MagicMock(
            return_value=
            self.context.agg_score_benchmark * 1.1)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertLess(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())
