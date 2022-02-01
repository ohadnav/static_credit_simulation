from loan_simulation_childs import NoCapitalLoanSimulation, IncreasingRebateLoanSimulation
from merchant import Merchant
from util_test import BaseTestCase


class TestNoCapitalLoanSimulation(BaseTestCase):
    def setUp(self) -> None:
        super(TestNoCapitalLoanSimulation, self).setUp()
        self.data_generator.num_products = 2
        self.data_generator.max_num_products = 5
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = NoCapitalLoanSimulation(self.context, self.data_generator, self.merchant)

    def test_add_debt(self):
        prev_cash = self.loan.current_cash
        amount1 = self.loan.max_debt()
        self.loan.add_debt(amount1)
        self.assertDeepAlmostEqual(self.loan.ledger.cash_history, {self.loan.today: self.loan.current_cash})
        self.assertEqual(self.loan.current_cash, prev_cash)
        self.assertEqual(self.loan.ledger.outstanding_balance(), 0)
        self.assertEqual(self.loan.ledger.total_credit(), 0)
        self.assertDeepAlmostEqual(self.loan.ledger.active_loans, [])

    def test_simulate(self):
        self.loan.simulate()
        self.assertEqual(self.loan.ledger.outstanding_balance(), 0)
        self.assertEqual(self.loan.ledger.total_credit(), 0)
        self.assertEqual(self.loan.simulation_results.effective_apr, 0)
        self.assertEqual(self.loan.simulation_results.debt_to_valuation, 0)
        self.assertEqual(self.loan.simulation_results.lender_profit, 0)

    def test_loan_amount(self):
        self.assertEqual(self.loan.loan_amount(), 0)


class TestIncreasingRebateLoanSimulation(BaseTestCase):
    def setUp(self) -> None:
        super(TestIncreasingRebateLoanSimulation, self).setUp()
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.increasing_rebate_loan = IncreasingRebateLoanSimulation(self.context, self.data_generator, self.merchant)

    def test_update_repayment_rate(self):
        self.increasing_rebate_loan.add_debt(self.increasing_rebate_loan.loan_amount())
        self.assertEqual(
            self.increasing_rebate_loan.current_repayment_rate, self.increasing_rebate_loan.default_repayment_rate())
        self.increasing_rebate_loan.today += self.context.loan_duration
        self.increasing_rebate_loan.update_repayment_rate()
        self.assertEqual(
            self.increasing_rebate_loan.current_repayment_rate,
            self.increasing_rebate_loan.default_repayment_rate() + self.context.delayed_loan_repayment_increase)
