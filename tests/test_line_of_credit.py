from unittest.mock import MagicMock, patch

from common import constants
from common.enum import LoanSimulationType
from common.numbers import ONE, TWO
from finance.line_of_credit import DynamicLineOfCreditSimulation, LineOfCreditSimulation, InvoiceFinancingSimulation
from seller.batch import Batch
from seller.merchant import Merchant
from tests.util_test import BaseTestCase


class TestLineOfCredit(BaseTestCase):
    def setUp(self) -> None:
        super(TestLineOfCredit, self).setUp()
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.line_of_credit = LineOfCreditSimulation(self.context, self.data_generator, self.merchant)
        self.line_of_credit.underwriting.approved = MagicMock(return_value=True)

    def test_remaining_credit(self):
        self.line_of_credit.approved_amount = MagicMock(return_value=self.line_of_credit.loan_amount())
        self.assertEqual(self.line_of_credit.remaining_credit(), self.line_of_credit.loan_amount())
        self.line_of_credit.add_debt(ONE)
        self.assertEqual(self.line_of_credit.remaining_credit(), self.line_of_credit.loan_amount() - 1)

    def test_update_credit(self):
        self.line_of_credit.credit_needed = MagicMock(return_value=0)
        self.line_of_credit.update_credit()
        self.assertEqual(self.line_of_credit.ledger.outstanding_balance(), 0)
        self.line_of_credit.credit_needed = MagicMock(return_value=1)
        prev_cash = self.line_of_credit.current_cash
        self.line_of_credit.update_credit()
        self.assertEqual(self.line_of_credit.current_cash, prev_cash + 1)
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

    @patch('finance.underwriting.Underwriting.aggregated_score')
    def test_repayment_rate_unchaged(self, aggregated_score_mock: MagicMock):
        aggregated_score_mock.return_value = self.context.agg_score_benchmark
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertEqual(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())

    @patch('finance.underwriting.Underwriting.aggregated_score')
    def test_repayment_rate_increase(self, aggregated_score_mock: MagicMock):
        aggregated_score_mock.return_value = self.context.agg_score_benchmark * 0.9
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertGreater(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())

    @patch('finance.underwriting.Underwriting.aggregated_score')
    def test_repayment_rate_decrease(self, aggregated_score_mock: MagicMock):
        aggregated_score_mock.return_value = self.context.agg_score_benchmark * 1.1
        self.dynamic_line_of_credit.update_repayment_rate()
        self.assertLess(
            self.dynamic_line_of_credit.current_repayment_rate,
            self.dynamic_line_of_credit.default_repayment_rate())


class TestInvoiceFinancingSimulation(BaseTestCase):
    def setUp(self) -> None:
        super(TestInvoiceFinancingSimulation, self).setUp()
        self.context.loan_type = LoanSimulationType.INVOICE_FINANCING
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.invoice_financing = InvoiceFinancingSimulation(self.context, self.data_generator, self.merchant)

    def test_approved_amount(self):
        batch1 = Batch.generate_simulated(self.data_generator)
        batch2 = Batch.generate_simulated(self.data_generator)
        batch1.max_cash_needed = MagicMock(return_value=ONE)
        batch2.max_cash_needed = MagicMock(return_value=TWO)
        self.invoice_financing.merchant.batches_with_orders = MagicMock(return_value=[batch1, batch2])
        self.invoice_financing.projected_lender_profit = MagicMock(return_value=ONE)
        self.invoice_financing.loan_amount = MagicMock(return_value=ONE + TWO)
        self.invoice_financing.underwriting.approved = MagicMock(side_effect=[True, False])
        self.assertEqual(self.invoice_financing.approved_amount(), batch1.max_cash_needed())
        self.invoice_financing.underwriting.approved = MagicMock(side_effect=[False, True])
        self.assertEqual(self.invoice_financing.approved_amount(), batch2.max_cash_needed())
        self.invoice_financing.underwriting.approved = MagicMock(side_effect=[True, True])
        self.assertEqual(self.invoice_financing.approved_amount(), self.invoice_financing.loan_amount())
