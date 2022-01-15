from copy import deepcopy
from dataclasses import fields
from random import uniform, randint
from unittest.mock import MagicMock

from common import constants
from common.util import inverse_cagr, O, ONE, Float, Dollar
from finance.loan_simulation import LoanSimulation, LoanSimulationResults, NoCapitalLoanSimulation, Loan
from seller.merchant import Merchant
from tests.util_test import BaseTestCase


class TestLoanSimulation(BaseTestCase):
    def setUp(self) -> None:
        super(TestLoanSimulation, self).setUp()
        self.data_generator.max_num_products = 4
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan_simulation = LoanSimulation(self.context, self.data_generator, self.merchant)

    def test_init(self):
        self.assertEqual(self.loan_simulation.outstanding_debt(), O)
        self.assertEqual(self.loan_simulation.total_credit, O)
        self.assertEqual(self.loan_simulation.total_revenues, O)
        self.assertDeepAlmostEqual(
            self.loan_simulation.cash_history, {self.loan_simulation.today: self.loan_simulation.initial_cash})
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [])

    def test_outstanding_debt(self):
        amount1 = self.loan_simulation.loan_amount()
        amount2 = amount1 / Float(2)
        self.loan_simulation.add_debt(amount1)
        debt1 = amount1 * (1 + self.loan_simulation.interest)
        self.assertAlmostEqual(self.loan_simulation.outstanding_debt(), debt1)
        self.loan_simulation.add_debt(amount2)
        debt2 = amount2 * (1 + self.loan_simulation.interest)
        self.assertAlmostEqual(self.loan_simulation.outstanding_debt(), debt1 + debt2)

    def test_default_repayment_rate(self):
        self.assertAlmostEqual(
            self.loan_simulation.default_repayment_rate(),
            self.loan_simulation.max_debt() / self.loan_simulation.expected_revenue_during_loan())
        self.loan_simulation.max_debt = MagicMock(return_value=100000000)
        self.assertEqual(self.loan_simulation.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)
        self.loan_simulation.max_debt = MagicMock(return_value=0)
        self.assertEqual(self.loan_simulation.default_repayment_rate(), constants.MIN_REPAYMENT_RATE)
        self.loan_simulation.expected_revenue_during_loan = MagicMock(return_value=0)
        self.assertEqual(self.loan_simulation.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)

    def test_expected_revenue_during_loan(self):
        self.context.loan_duration = constants.YEAR / 2
        self.assertAlmostEqual(
            self.loan_simulation.expected_revenue_during_loan(),
            self.merchant.annual_top_line(constants.START_DATE) * 0.5)

    def test_add_debt(self):
        with self.assertRaises(AssertionError):
            self.loan_simulation.add_debt(O)
        with self.assertRaises(AssertionError):
            self.loan_simulation.add_debt(-ONE)

        prev_cash = self.loan_simulation.current_cash
        amount1 = self.loan_simulation.loan_amount()
        amount2 = amount1 / Float(2)
        debt1 = self.loan_simulation.amount_to_debt(amount1)
        debt2 = self.loan_simulation.amount_to_debt(amount2)
        loan1 = Loan(amount1, self.context.loan_duration, debt1, self.loan_simulation.today)
        loan2 = Loan(amount2, self.context.loan_duration, debt2, self.loan_simulation.today + 1)

        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [])
        self.loan_simulation.add_debt(amount1)
        self.assertAlmostEqual(self.loan_simulation.current_cash, prev_cash + amount1)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan1])
        self.loan_simulation.today += 1
        self.loan_simulation.add_debt(amount2)
        self.assertAlmostEqual(self.loan_simulation.total_credit, debt1 + debt2)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan1, loan2])

    def test_max_debt(self):
        self.assertGreater(self.loan_simulation.max_debt(), self.loan_simulation.loan_amount())

    def test_credit_needed(self):
        inventory_cost = uniform(1, 1000)
        self.loan_simulation.current_cash = inventory_cost
        self.merchant.max_cash_needed = MagicMock(return_value=inventory_cost)
        self.assertEqual(self.loan_simulation.credit_needed(), 0)
        self.loan_simulation.current_cash = 0
        self.assertEqual(self.loan_simulation.credit_needed(), inventory_cost)
        self.loan_simulation.current_cash = 1
        self.assertAlmostEqual(self.loan_simulation.credit_needed(), inventory_cost - 1)

    def test_update_credit_new_credit(self):
        self.loan_simulation.current_repayment_rate = 0.1
        self.loan_simulation.credit_needed = MagicMock(return_value=self.loan_simulation.loan_amount())
        self.loan_simulation.approved_amount = MagicMock(return_value=self.loan_simulation.loan_amount())
        self.loan_simulation.default_repayment_rate = MagicMock(return_value=0.3)
        self.loan_simulation.add_debt = MagicMock()
        self.loan_simulation.update_credit()
        self.loan_simulation.add_debt.assert_called_with(self.loan_simulation.loan_amount())
        self.assertEqual(self.loan_simulation.current_repayment_rate, 0.3)

    def test_approved_amount(self):
        self.loan_simulation.loan_amount = MagicMock(return_value=1)
        self.loan_simulation.underwriting.approved = MagicMock(return_value=True)
        self.loan_simulation.projected_lender_profit = MagicMock(return_value=1)
        self.assertEqual(self.loan_simulation.approved_amount(), 1)
        self.loan_simulation.underwriting.approved = MagicMock(return_value=False)
        self.assertEqual(self.loan_simulation.approved_amount(), 0)
        self.loan_simulation.underwriting.approved = MagicMock(return_value=True)
        self.loan_simulation.projected_lender_profit = MagicMock(return_value=-1)
        self.assertEqual(self.loan_simulation.approved_amount(), 0)

    def test_simulate_day(self):
        self.loan_simulation.update_credit = MagicMock()
        self.loan_simulation.simulate_sales = MagicMock()
        self.loan_simulation.simulate_inventory_purchase = MagicMock()
        self.loan_simulation.marketplace_payout = MagicMock()
        self.loan_simulation.on_bankruptcy = MagicMock()
        self.loan_simulation.current_cash = 1
        self.loan_simulation.simulate_day()
        self.loan_simulation.update_credit.assert_called()
        self.loan_simulation.simulate_sales.assert_called()
        self.loan_simulation.simulate_inventory_purchase.assert_called()
        self.loan_simulation.marketplace_payout.assert_called()
        self.loan_simulation.on_bankruptcy.assert_not_called()
        self.assertDeepAlmostEqual(
            self.loan_simulation.cash_history, {self.loan_simulation.today: self.loan_simulation.initial_cash})
        self.loan_simulation.today += 1
        self.loan_simulation.current_cash = -1
        self.loan_simulation.simulate_day()
        self.loan_simulation.on_bankruptcy.assert_called()

    def test_simulate_sales(self):
        self.loan_simulation.marketplace_balance = 1
        self.loan_simulation.total_revenues = 2
        self.loan_simulation.simulate_sales()
        self.assertAlmostEqual(
            self.loan_simulation.marketplace_balance, 1 + self.merchant.gp_per_day(constants.START_DATE))
        self.assertAlmostEqual(
            self.loan_simulation.total_revenues, 2 + self.merchant.revenue_per_day(constants.START_DATE))

    def test_simulate_inventory_purchase(self):
        self.loan_simulation.current_cash = 2
        self.merchant.inventory_cost = MagicMock(return_value=1)
        self.loan_simulation.simulate_inventory_purchase()
        self.assertEqual(self.loan_simulation.current_cash, 2 - 1)
        self.assertDeepAlmostEqual(self.loan_simulation.cash_history, {constants.START_DATE: ONE})

    def test_marketplace_payout_bankruptcy(self):
        self.loan_simulation.today = constants.MARKETPLACE_PAYMENT_CYCLE
        self.loan_simulation.marketplace_balance = 0
        self.loan_simulation.merchant.has_future_revenue = MagicMock(return_value=False)
        self.loan_simulation.on_bankruptcy = MagicMock()
        self.loan_simulation.marketplace_payout()
        self.loan_simulation.on_bankruptcy.assert_called()

    def test_marketplace_payout(self):
        self.loan_simulation.today = constants.MARKETPLACE_PAYMENT_CYCLE + 1
        self.loan_simulation.loan_repayment = MagicMock()
        self.loan_simulation.marketplace_balance = 1
        self.loan_simulation.current_cash = 2
        self.loan_simulation.marketplace_payout()
        self.loan_simulation.loan_repayment.assert_not_called()
        self.assertEqual(self.loan_simulation.current_cash, 2)
        self.assertEqual(self.loan_simulation.marketplace_balance, 1)
        self.loan_simulation.today = constants.MARKETPLACE_PAYMENT_CYCLE
        self.loan_simulation.marketplace_payout()
        self.loan_simulation.loan_repayment.assert_called()
        self.assertEqual(self.loan_simulation.current_cash, 2 + 1)
        self.assertEqual(self.loan_simulation.marketplace_balance, 0)
        self.assertDeepAlmostEqual(
            self.loan_simulation.cash_history,
            {constants.START_DATE: self.loan_simulation.initial_cash, self.loan_simulation.today: 3})

    def test_simulate(self):
        self.loan_simulation.calculate_results = MagicMock()
        self.loan_simulation.simulate_day = MagicMock()
        self.loan_simulation.simulate()
        self.loan_simulation.calculate_results.assert_called()
        self.assertEqual(self.loan_simulation.simulate_day.call_count, self.data_generator.simulated_duration)
        self.assertEqual(self.loan_simulation.today, self.data_generator.simulated_duration)

    def test_simulate_not_random(self):
        self.data_generator.simulated_duration = constants.YEAR
        self.data_generator.normal_ratio = MagicMock(return_value=1)
        self.data_generator.random = MagicMock(return_value=1)
        self.loan_simulation.simulate()
        self.data_generator.normal_ratio.assert_not_called()
        self.data_generator.random.assert_not_called()

    def test_simulate_deterministic(self):
        self.data_generator.simulated_duration = constants.YEAR
        loan2 = deepcopy(self.loan_simulation)
        self.loan_simulation.simulate()
        loan2.simulate()
        for field in fields(self.loan_simulation.simulation_results):
            val1 = getattr(self.loan_simulation.simulation_results, field.name)
            val2 = getattr(loan2.simulation_results, field.name)
            if isinstance(val1, bool):
                self.assertEqual(val1, val2)
            self.assertAlmostEqual(val1, val2)
        for day in self.loan_simulation.cash_history.keys():
            self.assertAlmostEqual(self.loan_simulation.cash_history[day], loan2.cash_history[day])

    def test_simulate_bankruptcy(self):
        self.loan_simulation.simulate_day = MagicMock()
        self.loan_simulation.calculate_results = MagicMock()
        self.loan_simulation.bankruptcy_date = True
        self.loan_simulation.simulate()
        self.assertEqual(self.loan_simulation.simulate_day.call_count, 1)
        self.assertEqual(self.loan_simulation.today, constants.START_DATE)

    def test_loan_repayment(self):
        amount1 = self.loan_simulation.loan_amount()
        self.loan_simulation.marketplace_balance = ONE
        self.loan_simulation.current_repayment_rate = Float(0.1)
        repaid1 = self.loan_simulation.marketplace_balance * self.loan_simulation.current_repayment_rate
        self.loan_simulation.loan_repayment()
        self.assertAlmostEqual(self.loan_simulation.current_cash, self.loan_simulation.initial_cash)
        self.loan_simulation.add_debt(amount1)
        self.loan_simulation.loan_repayment()
        self.assertAlmostEqual(self.loan_simulation.current_cash, self.loan_simulation.initial_cash + amount1 - repaid1)
        debt1 = self.loan_simulation.amount_to_debt(amount1)
        self.assertAlmostEqual(self.loan_simulation.outstanding_debt(), debt1 - repaid1)
        self.assertAlmostEqual(self.loan_simulation.active_loans[0].outstanding_debt, debt1 - repaid1)
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [])
        self.loan_simulation.marketplace_balance = debt1 * 10
        self.loan_simulation.loan_repayment()
        self.assertAlmostEqual(self.loan_simulation.current_cash, self.loan_simulation.initial_cash + amount1 - debt1)
        self.assertAlmostEqual(self.loan_simulation.outstanding_debt(), O)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [Loan(amount1, 1, O, constants.START_DATE)])

    def test_close_all_loans(self):
        loan1 = Loan(ONE, self.context.loan_duration, self.loan_simulation.amount_to_debt(ONE), constants.START_DATE)
        amount2 = Dollar(2)
        amount3 = Dollar(3)
        loan2 = Loan(
            amount2, self.context.loan_duration, self.loan_simulation.amount_to_debt(amount2), constants.START_DATE)
        loan3 = Loan(
            amount3, self.context.loan_duration, self.loan_simulation.amount_to_debt(amount3), constants.START_DATE)
        self.loan_simulation.add_debt(ONE)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan1])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [])
        self.loan_simulation.close_all_loans()
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [loan1])
        self.loan_simulation.add_debt(amount2)
        self.loan_simulation.add_debt(amount3)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan2, loan3])
        self.loan_simulation.close_all_loans()
        self.assertDeepAlmostEqual(
            self.loan_simulation.loans_history, [loan1, loan2, loan3])
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [])

    def test_repay_loans(self):
        amount1 = Dollar(1)
        amount2 = Dollar(2)
        debt1 = self.loan_simulation.amount_to_debt(amount1)
        loan1 = Loan(
            amount1, self.context.loan_duration, debt1, constants.START_DATE)
        debt2 = self.loan_simulation.amount_to_debt(amount2)
        loan2 = Loan(
            amount2, self.context.loan_duration, debt2, constants.START_DATE)
        repaid1 = Dollar(0.5)
        repaid2 = loan1.outstanding_debt - repaid1 + 1
        loan1_mid = Loan(loan1.amount, loan1.duration, loan1.outstanding_debt - repaid1, loan1.start_date)
        loan1_end = Loan(loan1.amount, 1, O, loan1.start_date)
        loan2_mid = Loan(loan2.amount, loan2.duration, loan2.outstanding_debt - 1, loan2.start_date)
        loan2_end = Loan(loan2.amount, 1, O, loan2.start_date)
        self.loan_simulation.add_debt(amount1)
        self.loan_simulation.add_debt(amount2)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan1, loan2])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [])
        self.loan_simulation.repay_loans(repaid1)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan1_mid, loan2])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [])
        self.loan_simulation.repay_loans(repaid2)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan2_mid])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [loan1_end])
        self.loan_simulation.repay_loans(self.loan_simulation.outstanding_debt())
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [loan1_end, loan2_end])

    def test_close_active_loan(self):
        amount1 = Dollar(1)
        amount2 = Dollar(2)
        loan1 = Loan(
            amount1, self.context.loan_duration, self.loan_simulation.amount_to_debt(amount1), constants.START_DATE)
        debt2 = self.loan_simulation.amount_to_debt(amount2)
        loan2 = Loan(
            amount2, self.context.loan_duration, debt2, constants.START_DATE)
        self.loan_simulation.add_debt(amount1)
        self.loan_simulation.add_debt(amount2)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan1, loan2])
        self.loan_simulation.close_active_loan()
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [loan2])
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [loan1])
        self.loan_simulation.repay_loans(debt2)
        self.assertDeepAlmostEqual(self.loan_simulation.active_loans, [])
        loan2_paid = Loan(loan2.amount, 1, O, loan2.start_date)
        self.assertDeepAlmostEqual(self.loan_simulation.loans_history, [loan1, loan2_paid])

    def test_on_bankruptcy(self):
        self.loan_simulation.today = randint(constants.START_DATE, self.data_generator.simulated_duration)
        self.loan_simulation.on_bankruptcy()
        self.assertEqual(self.loan_simulation.bankruptcy_date, self.loan_simulation.today)

    def test_calculate_results(self):
        self.loan_simulation.merchant.valuation = MagicMock(return_value=0)
        self.loan_simulation.revenue_cagr = MagicMock(return_value=1)
        self.loan_simulation.inventory_cagr = MagicMock(return_value=2)
        self.loan_simulation.net_cashflow_cagr = MagicMock(return_value=3)
        self.loan_simulation.valuation_cagr = MagicMock(return_value=4)
        self.loan_simulation.lender_profit = MagicMock(return_value=5)
        self.loan_simulation.debt_to_loan_amount = MagicMock(return_value=6)
        self.loan_simulation.debt_to_valuation = MagicMock(return_value=7)
        self.loan_simulation.average_apr = MagicMock(return_value=8)
        self.loan_simulation.calculate_bankruptcy_rate = MagicMock(return_value=9)
        self.loan_simulation.calculate_results()
        # noinspection PyTypeChecker
        self.assertEqual(self.loan_simulation.simulation_results, LoanSimulationResults(0, 1, 2, 3, 4, 5, 6, 7, 8, 9))

    def test_calculate_bankruptcy_rate(self):
        self.loan_simulation.bankruptcy_date = None
        self.assertEqual(self.loan_simulation.calculate_bankruptcy_rate(), 0)
        self.loan_simulation.bankruptcy_date = self.data_generator.simulated_duration / 10 + constants.START_DATE
        self.assertEqual(self.loan_simulation.calculate_bankruptcy_rate(), 0.9)
        self.loan_simulation.bankruptcy_date = constants.START_DATE
        self.assertAlmostEqual(self.loan_simulation.calculate_bankruptcy_rate(), 1)
        self.loan_simulation.bankruptcy_date = self.data_generator.simulated_duration
        self.assertAlmostEqual(
            self.loan_simulation.calculate_bankruptcy_rate(),
            1 / self.data_generator.simulated_duration)

    def test_net_cashflow(self):
        self.assertEqual(self.loan_simulation.net_cashflow(), self.loan_simulation.initial_cash)
        amount = ONE
        debt = self.loan_simulation.amount_to_debt(amount)
        self.loan_simulation.add_debt(amount)
        self.assertEqual(self.loan_simulation.net_cashflow(), self.loan_simulation.initial_cash + amount - debt)

    def test_valuation_cagr(self):
        self.loan_simulation.today = constants.YEAR
        self.merchant.valuation = MagicMock(side_effect=[1, 3])
        self.assertAlmostEqual(self.loan_simulation.valuation_cagr(), 2)

    def test_inventory_cagr(self):
        self.loan_simulation.today = constants.YEAR
        self.merchant.inventory_value = MagicMock(side_effect=[1, 3])
        self.assertAlmostEqual(self.loan_simulation.inventory_cagr(), 2)

    def test_net_cashflow_cagr(self):
        self.loan_simulation.today = constants.YEAR
        self.loan_simulation.current_cash = self.loan_simulation.initial_cash * 2
        self.assertAlmostEqual(self.loan_simulation.net_cashflow_cagr(), 1)

    def test_revenue_cagr(self):
        self.loan_simulation.today = constants.YEAR
        self.merchant.annual_top_line = MagicMock(side_effect=[1, 3])
        self.loan_simulation.total_revenues = 1.5
        self.assertAlmostEqual(self.loan_simulation.revenue_cagr(), 0.5)

    def test_is_default(self):
        self.assertFalse(self.loan_simulation.is_default())
        self.loan_simulation.on_bankruptcy()
        self.assertTrue(self.loan_simulation.is_default())
        self.loan_simulation.bankruptcy_date = None
        self.context.duration_based_default = True
        self.loan_simulation.add_debt(ONE)
        self.assertFalse(self.loan_simulation.is_default())
        self.loan_simulation.today = self.context.loan_duration + 1
        self.assertTrue(self.loan_simulation.is_default())
        self.context.duration_based_default = False
        self.assertFalse(self.loan_simulation.is_default())

    def test_loss_default(self):
        self.assertEqual(self.loan_simulation.loss(), 0)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.loan_simulation.is_default = MagicMock(return_value=True)
        self.assertAlmostEqual(self.loan_simulation.loss(), self.loan_simulation.loan_amount())
        self.loan_simulation.repaid_debt = MagicMock(return_value=self.loan_simulation.loan_amount())
        self.assertAlmostEqual(self.loan_simulation.loss(), 0)

    def test_loss_non_default(self):
        self.loan_simulation.is_default = MagicMock(return_value=False)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.context.loan_duration = 1
        self.assertAlmostEqual(
            self.loan_simulation.loss(), self.loan_simulation.loan_amount() - self.merchant.annual_top_line(
                self.loan_simulation.today) * self.loan_simulation.current_repayment_rate / constants.YEAR)

    def test_cost_of_capital(self):
        self.loan_simulation.loan_amount = MagicMock(return_value=10)
        amount = self.loan_simulation.loan_amount()
        self.loan_simulation.add_debt(amount)
        actual_coc_rate = inverse_cagr(self.context.cost_of_capital, self.context.loan_duration)
        self.assertAlmostEqual(
            self.loan_simulation.cost_of_capital(), actual_coc_rate * amount)
        self.loan_simulation.today = constants.START_DATE + constants.YEAR - 1
        self.assertAlmostEqual(
            self.loan_simulation.cost_of_capital(), self.context.cost_of_capital * amount)
        self.loan_simulation.repay_loans(self.loan_simulation.outstanding_debt())
        self.assertAlmostEqual(
            self.loan_simulation.cost_of_capital(), self.context.cost_of_capital * amount)
        self.loan_simulation.add_debt(amount)
        self.loan_simulation.today += self.context.loan_duration - 1
        self.loan_simulation.repay_loans(self.loan_simulation.outstanding_debt())
        self.assertAlmostEqual(
            self.loan_simulation.cost_of_capital(),
            actual_coc_rate * amount + amount *
            self.context.cost_of_capital)

    def test_repaid_debt(self):
        self.loan_simulation.total_credit = 10
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=6)
        self.assertAlmostEqual(self.loan_simulation.repaid_debt(), 4)

    def test_projected_remaining_debt_non_default(self):
        self.loan_simulation.is_default = MagicMock(return_value=False)
        self.loan_simulation.remaining_duration = MagicMock(return_value=2)
        self.loan_simulation.merchant.annual_top_line = MagicMock(return_value=3 * constants.YEAR)
        self.loan_simulation.current_repayment_rate = 4
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertAlmostEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.max_debt() - 2 * 3 * 4)
        self.loan_simulation.repay_loans(ONE)
        self.assertAlmostEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.max_debt() - 1 - 2 * 3 * 4)

    def test_projected_remaining_debt_default(self):
        self.loan_simulation.is_default = MagicMock(return_value=True)
        self.assertAlmostEqual(self.loan_simulation.projected_remaining_debt(), 0)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertAlmostEqual(self.loan_simulation.projected_remaining_debt(), self.loan_simulation.outstanding_debt())
        repaid = Dollar(1)
        self.loan_simulation.repay_loans(repaid)
        self.assertAlmostEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.max_debt() - repaid)

    def test_debt_to_valuation(self):
        self.merchant.valuation = MagicMock(return_value=2)
        self.assertAlmostEqual(self.loan_simulation.debt_to_valuation(), 0)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertAlmostEqual(self.loan_simulation.debt_to_valuation(), self.loan_simulation.max_debt() / 2)

    def test_lender_profit(self):
        self.assertEqual(self.loan_simulation.lender_profit(), 0)
        self.loan_simulation.is_default = MagicMock(return_value=True)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        prev_loss = self.loan_simulation.loss()
        prev_coc = self.loan_simulation.cost_of_capital()
        max_costs = prev_loss + prev_coc + self.context.merchant_cost_of_acquisition
        self.assertEqual(self.loan_simulation.lender_profit(), -max_costs)
        repaid = Dollar(2)
        self.loan_simulation.repay_loans(repaid)
        new_loss = prev_loss - repaid
        new_revenue = repaid * self.loan_simulation.average_apr()
        new_costs = new_loss + prev_coc + self.context.merchant_cost_of_acquisition
        self.assertAlmostEqual(self.loan_simulation.lender_profit(), new_revenue - new_costs)

    def test_projected_lender_profit(self):
        self.loan_simulation.loan_amount = MagicMock(return_value=10)
        self.loan_simulation.calculate_apr = MagicMock(return_value=0.1)
        self.context.merchant_cost_of_acquisition = 1
        self.context.cost_of_capital = 0.5
        self.context.loan_duration = 60
        self.context.expected_loans_per_year = 6
        projected_costs = self.context.merchant_cost_of_acquisition + 10 * inverse_cagr(ONE / 2, 60) * 6
        projected_revenues = 10 * 0.1 * 6
        self.assertAlmostEqual(self.loan_simulation.projected_lender_profit(), projected_revenues - projected_costs)
        self.loan_simulation.total_credit = 1
        projected_costs2 = 10 * inverse_cagr(ONE / 2, 60) * 1
        projected_revenues2 = 10 * 0.1 * 1
        self.assertAlmostEqual(
            self.loan_simulation.projected_lender_profit(),
            projected_revenues2 - projected_costs2)

    def test_calculate_apr(self):
        self.assertAlmostEqual(self.loan_simulation.calculate_apr(constants.YEAR), self.loan_simulation.interest)
        self.assertAlmostEqual(
            self.loan_simulation.calculate_apr(constants.YEAR / 2), (self.loan_simulation.interest + 1) ** 2 - 1)

    def test_average_apr(self):
        amount1 = ONE * 2
        amount2 = ONE
        apr1 = self.loan_simulation.calculate_apr(self.context.loan_duration)
        apr2 = self.loan_simulation.calculate_apr(self.context.loan_duration / 2)
        self.loan_simulation.add_debt(amount1)
        self.assertAlmostEqual(self.loan_simulation.average_apr(), apr1)
        self.loan_simulation.today = constants.START_DATE + self.context.loan_duration / 2
        self.assertAlmostEqual(self.loan_simulation.average_apr(), apr1)
        self.loan_simulation.add_debt(amount2)
        self.loan_simulation.today = constants.START_DATE + self.context.loan_duration - 1
        self.assertAlmostEqual(self.loan_simulation.average_apr(), apr1)
        self.loan_simulation.repay_loans(self.loan_simulation.outstanding_debt())
        self.assertAlmostEqual(self.loan_simulation.average_apr(), (2 * apr1 + apr2) / 3)

    def test_average_apr_long_loans(self):
        amount1 = ONE * 2
        amount2 = ONE
        apr0 = self.loan_simulation.calculate_apr(self.context.loan_duration)
        apr1 = self.loan_simulation.calculate_apr(self.context.loan_duration * 3)
        apr2 = self.loan_simulation.calculate_apr(self.context.loan_duration * 2 + 1)
        self.loan_simulation.add_debt(amount1)
        self.assertAlmostEqual(self.loan_simulation.average_apr(), apr0)
        self.loan_simulation.today = constants.START_DATE + self.context.loan_duration - 1
        self.loan_simulation.add_debt(amount2)
        self.assertAlmostEqual(self.loan_simulation.average_apr(), apr0)
        self.loan_simulation.today = constants.START_DATE + 3 * self.context.loan_duration - 1
        self.assertAlmostEqual(self.loan_simulation.average_apr(), (2 * apr1 + apr2) / 3)
        self.loan_simulation.repay_loans(self.loan_simulation.outstanding_debt())
        self.assertAlmostEqual(self.loan_simulation.average_apr(), (2 * apr1 + apr2) / 3)


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
        self.assertDeepAlmostEqual(self.loan.cash_history, {self.loan.today: self.loan.current_cash})
        self.assertAlmostEqual(self.loan.current_cash, prev_cash)
        self.assertAlmostEqual(self.loan.outstanding_debt(), 0)
        self.assertAlmostEqual(self.loan.total_credit, 0)
        self.assertDeepAlmostEqual(self.loan.active_loans, [])

    def test_simulate(self):
        self.loan.simulate()
        self.assertAlmostEqual(self.loan.outstanding_debt(), 0)
        self.assertAlmostEqual(self.loan.total_credit, 0)
        self.assertAlmostEqual(self.loan.simulation_results.apr, 0)
        self.assertAlmostEqual(self.loan.simulation_results.debt_to_valuation, 0)
        self.assertAlmostEqual(self.loan.simulation_results.lender_profit, 0)

    def test_loan_amount(self):
        self.assertEqual(self.loan.loan_amount(), 0)
