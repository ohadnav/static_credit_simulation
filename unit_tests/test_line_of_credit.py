import logging
import sys
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE, logged, traced

from common import constants
from common.constants import LoanType
from common.context import SimulationContext, DataGenerator
from finance.line_of_credit import DynamicLineOfCredit, LineOfCredit
from seller.merchant import Merchant


@traced
@logged
class TestLineOfCredit(TestCase):
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
        self.context = SimulationContext(loan_type=LoanType.LINE_OF_CREDIT)
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.line_of_credit = LineOfCredit(self.context, self.data_generator, self.merchant)
        self.line_of_credit.underwriting.approved = MagicMock(return_value=True)

    def test_remaining_credit(self):
        self.assertEqual(self.line_of_credit.remaining_credit(), self.line_of_credit.loan_amount())
        self.line_of_credit.add_debt(1)
        self.assertEqual(self.line_of_credit.remaining_credit(), self.line_of_credit.loan_amount() - 1)

    def test_update_credit(self):
        self.line_of_credit.credit_needed = MagicMock(return_value=0)
        self.line_of_credit.update_credit()
        self.assertEqual(self.line_of_credit.outstanding_debt, 0)
        self.line_of_credit.credit_needed = MagicMock(return_value=1)
        prev_cash = self.line_of_credit.current_cash
        self.line_of_credit.update_credit()
        self.assertAlmostEqual(self.line_of_credit.current_cash, prev_cash + 1)
        self.line_of_credit.remaining_credit = MagicMock(return_value=0)
        self.line_of_credit.update_credit()
        self.assertEqual(self.line_of_credit.current_cash, prev_cash + 1)


@traced
@logged
class TestDynamicLineOfCredit(TestCase):
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
        self.context = SimulationContext(loan_type=LoanType.DYNAMIC_LINE_OF_CREDIT)
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.dynamic_line_of_credit = DynamicLineOfCredit(self.context, self.data_generator, self.merchant)
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
        self.dynamic_line_of_credit.underwriting.aggregated_score = MagicMock(return_value=constants.REPAYMENT_FACTOR)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertEqual(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())

    def test_repayment_rate_increase(self):
        self.dynamic_line_of_credit.underwriting.aggregated_score = MagicMock(
            return_value=constants.REPAYMENT_FACTOR * 0.9)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertGreater(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())

    def test_repayment_rate_decrease(self):
        self.dynamic_line_of_credit.underwriting.aggregated_score = MagicMock(
            return_value=constants.REPAYMENT_FACTOR * 1.1)
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertLess(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())
