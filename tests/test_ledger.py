from copy import deepcopy

from common.numbers import Dollar, ONE, ONE_INT, TWO, O, TWO_INT, Duration, O_INT, Date
from finance.ledger import Ledger, Loan, Repayment
from tests.util_test import BaseTestCase

HALF = Dollar(0.5)


class TestLedger(BaseTestCase):
    def setUp(self) -> None:
        super(TestLedger, self).setUp()
        self.ledger = Ledger(self.data_generator, self.context)
        self.one_loan = Loan(ONE, ONE, ONE_INT)
        self.one_loan_paid = Loan(ONE, O, ONE_INT)

    def test_outstanding_balance(self):
        self.ledger.new_loan(self.one_loan)
        self.ledger.new_loan(self.one_loan)
        self.assertEqual(self.ledger.outstanding_balance(), TWO)
        self.assertEqual(self.ledger.outstanding_balance([self.one_loan]), ONE)

    def test_repayments_from_amount_empty_result(self):
        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(ONE_INT, O), [])
        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(ONE_INT, ONE), [])
        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(ONE_INT, ONE), [])
        self.ledger.new_loan(self.one_loan)
        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(ONE_INT, O), [])

    def test_repayments_from_amount_single_loan(self):
        self.ledger.new_loan(self.one_loan)
        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(ONE_INT, ONE), [Repayment(ONE_INT, ONE, ONE_INT)])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [])

    def test_repayments_from_amount_multiple_loans(self):
        HALF = Dollar(0.5)
        three = Duration(3)
        loan2 = Loan(ONE, ONE, TWO_INT)
        loan2_mid = Loan(ONE, HALF, TWO_INT)
        loan2_paid = Loan(ONE, O, TWO_INT)
        repayment1 = Repayment(TWO_INT, ONE, TWO_INT)
        repayment2 = Repayment(TWO_INT, HALF, ONE_INT)
        repayment3 = Repayment(three, HALF, TWO_INT)

        self.ledger.new_loan(deepcopy(self.one_loan))
        self.ledger.new_loan(deepcopy(loan2))
        self.assertDeepAlmostEqual(
            self.ledger.repayments_from_amount(TWO_INT, ONE + HALF), [repayment1, repayment2])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [loan2_mid])
        self.assertDeepAlmostEqual(self.ledger.loans_history, [self.one_loan, loan2])
        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(three, HALF), [repayment3])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [])
        self.assertDeepAlmostEqual(self.ledger.loans_history, [self.one_loan, loan2])

    def test_repayments_from_amount_non_self_loans(self):
        three = Duration(3)
        loan2 = Loan(ONE, ONE, TWO_INT)
        loan2_mid = Loan(ONE, HALF, TWO_INT)
        loan2_paid = Loan(ONE, O, TWO_INT)
        repayment1 = Repayment(TWO_INT, ONE, TWO_INT)
        repayment2 = Repayment(TWO_INT, HALF, ONE_INT)
        repayment3 = Repayment(three, HALF, TWO_INT)
        loans = [self.one_loan, loan2]

        self.assertDeepAlmostEqual(self.ledger.active_loans, [])
        self.assertDeepAlmostEqual(
            self.ledger.repayments_from_amount(TWO_INT, ONE + HALF, loans), [repayment1, repayment2])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [])
        self.assertDeepAlmostEqual(loans, [loan2_mid])
        self.assertEqual(self.one_loan.outstanding_balance, O)
        self.assertEqual(loan2.outstanding_balance, HALF)

        self.assertDeepAlmostEqual(self.ledger.repayments_from_amount(three, HALF, loans), [repayment3])
        self.assertDeepAlmostEqual(loans, [])
        self.assertEqual(loan2.outstanding_balance, O)

    def test_initiate_loan_repayment(self):
        three = Duration(3)
        loan2 = Loan(ONE, ONE, TWO_INT)
        loan2_mid = Loan(ONE, HALF, TWO_INT)
        loan2_paid = Loan(ONE, O, TWO_INT)
        repayment1 = Repayment(TWO_INT, ONE, TWO_INT)
        repayment2 = Repayment(TWO_INT, HALF, ONE_INT)
        repayment3 = Repayment(three, HALF, TWO_INT)
        self.ledger.new_loan(deepcopy(self.one_loan))
        self.ledger.new_loan(deepcopy(loan2))
        self.ledger.initiate_loan_repayment(TWO_INT, ONE + HALF)
        self.assertDeepAlmostEqual(self.ledger.repayments, [repayment1, repayment2])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [loan2_mid])
        self.ledger.initiate_loan_repayment(three, ONE)
        self.assertDeepAlmostEqual(self.ledger.repayments, [repayment1, repayment2, repayment3])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [])
        self.assertDeepAlmostEqual(self.ledger.loans_history, [self.one_loan, loan2])

    def test_initiate_loan_repayment_no_repayment(self):
        self.ledger.initiate_loan_repayment(ONE_INT, ONE)
        self.assertDeepAlmostEqual(self.ledger.repayments, [])
        self.ledger.new_loan(self.one_loan)
        self.ledger.initiate_loan_repayment(ONE_INT, O)
        self.assertDeepAlmostEqual(self.ledger.repayments, [])

    def test_projected_repayments(self):
        cent = Dollar(0.01)
        today = Date(TWO_INT)
        loan2 = Loan(ONE, ONE, today)
        repayments_HALF = [
            Repayment(
                ONE_INT + 1 * self.context.marketplace_payment_cycle, HALF,
                ONE_INT + 1 * self.context.marketplace_payment_cycle),
            Repayment(
                ONE_INT + 2 * self.context.marketplace_payment_cycle, HALF,
                ONE_INT + 2 * self.context.marketplace_payment_cycle),
            Repayment(
                ONE_INT + 3 * self.context.marketplace_payment_cycle, HALF,
                O_INT + 3 * self.context.marketplace_payment_cycle),
            Repayment(
                ONE_INT + 4 * self.context.marketplace_payment_cycle, HALF,
                O_INT + 4 * self.context.marketplace_payment_cycle),
        ]
        repayments_cent = [Repayment(
            ONE_INT + (i + 1) * self.context.marketplace_payment_cycle, cent,
            ONE_INT + (i + 1) * self.context.marketplace_payment_cycle) for i in
            range((self.context.loan_duration / self.context.marketplace_payment_cycle).floor() - 1)]
        self.ledger.new_loan(deepcopy(self.one_loan))
        self.ledger.new_loan(deepcopy(loan2))

        self.assertDeepAlmostEqual(self.ledger.projected_repayments(self.ledger.outstanding_balance(), today, HALF), [])
        self.assertDeepAlmostEqual(self.ledger.projected_repayments(O, today, O), [])
        self.assertDeepAlmostEqual(self.ledger.projected_repayments(O, today, HALF), repayments_HALF)
        self.assertDeepAlmostEqual(self.ledger.projected_repayments(O, today, cent), repayments_cent)
        self.assertDeepAlmostEqual(self.ledger.projected_repayments(ONE, today, HALF), repayments_HALF[:2])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [self.one_loan, loan2])

    def test_undo_active_loans(self):
        repaid = Dollar(0.6)
        self.ledger.new_loan(deepcopy(self.one_loan))
        self.ledger.undo_active_loans()
        self.assertEqual(self.ledger.total_credit(), O)
        self.assertEqual(self.ledger.outstanding_balance(), O)
        self.assertDeepAlmostEqual(self.ledger.loans_history, [])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [])
        self.ledger.new_loan(deepcopy(Loan(repaid, repaid * 2, ONE_INT)))
        self.ledger.initiate_loan_repayment(ONE_INT, repaid)
        self.ledger.undo_active_loans()
        self.assertDeepAlmostEqual(self.ledger.loans_history, [Loan(repaid / 2, repaid, ONE_INT)])
        self.assertDeepAlmostEqual(self.ledger.active_loans, [])
        self.assertEqual(self.ledger.outstanding_balance(), O)
        self.assertEqual(self.ledger.total_credit(), repaid / 2)


class TestRepayment(BaseTestCase):
    def test_generate_from_loan(self):
        three = Duration(3)
        self.assertEqual(
            Repayment.generate_from_loan(three, Loan(ONE, ONE, ONE_INT), ONE),
            Repayment(three, ONE, three.from_date(ONE)))

    def test_repay(self):
        HALF = Dollar(0.5)
        repayment = Repayment(ONE_INT, HALF, ONE_INT)
        loan1 = Loan(HALF, ONE, ONE_INT)
        loan1_mid = Loan(HALF, HALF, ONE_INT)
        loan1_repaid = Loan(HALF, O, ONE_INT)
        loan2 = Loan(HALF, HALF, ONE_INT)
        loan2_repaid = Loan(HALF, O, ONE_INT)
        loans = [loan1, loan2]
        repayment.repay(loans)
        self.assertDeepAlmostEqual(loans, [loan1_mid, loan2])
        self.assertEqual(loan1, loan1_mid)
        repayment.repay(loans)
        self.assertDeepAlmostEqual(loans, [loan2])
        self.assertEqual(loan1, loan1_repaid)
        repayment.repay(loans)
        self.assertDeepAlmostEqual(loans, [])
        self.assertEqual(loan2, loan2_repaid)
