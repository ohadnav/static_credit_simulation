from copy import deepcopy
from dataclasses import fields
from random import uniform, randint
from unittest.mock import MagicMock

from common import constants
from common.enum import LoanReferenceType
from common.numbers import Float, Dollar, O, ONE, TWO, Duration, O_INT, Ratio, Int, Date, ONE_INT, Percent
from finance.ledger import Loan, Repayment
from finance.loan_simulation import LoanSimulation, NoCapitalLoanSimulation
from finance.loan_simulation_results import LoanSimulationResults
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
        self.assertEqual(self.loan_simulation.ledger.outstanding_balance(), O)
        self.assertEqual(self.loan_simulation.ledger.total_credit(), O)
        self.assertEqual(self.loan_simulation.revenues_to_date, O)
        self.assertEqual(self.loan_simulation.ledger.get_num_loans(), O_INT)
        self.assertDeepAlmostEqual(
            self.loan_simulation.ledger.cash_history, {self.loan_simulation.today: self.loan_simulation.initial_cash})

    def test_outstanding_debt(self):
        amount1 = self.loan_simulation.loan_amount()
        amount2 = amount1 / TWO
        self.loan_simulation.add_debt(amount1)
        debt1 = self.loan_simulation.amount_to_debt(amount1)
        self.assertEqual(self.loan_simulation.ledger.outstanding_balance(), debt1)
        self.loan_simulation.add_debt(amount2)
        debt2 = self.loan_simulation.amount_to_debt(amount2)
        self.assertEqual(self.loan_simulation.ledger.outstanding_balance(), debt1 + debt2)

    def test_default_repayment_rate(self):
        self.assertEqual(
            self.loan_simulation.default_repayment_rate(),
            self.loan_simulation.max_debt() / self.loan_simulation.expected_revenue_during_loan())
        self.loan_simulation.max_debt = MagicMock(return_value=100000000)
        self.assertEqual(self.loan_simulation.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)
        self.loan_simulation.max_debt = MagicMock(return_value=Dollar(0))
        self.assertEqual(self.loan_simulation.default_repayment_rate(), constants.MIN_REPAYMENT_RATE)
        self.loan_simulation.expected_revenue_during_loan = MagicMock(return_value=Dollar(0))
        self.assertEqual(self.loan_simulation.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)

    def test_expected_revenue_during_loan(self):
        self.context.loan_duration = Date(constants.YEAR) / 2
        self.assertEqual(
            self.loan_simulation.expected_revenue_during_loan(),
            self.merchant.annual_top_line(self.data_generator.start_date) * 0.5)

    def test_add_debt(self):
        with self.assertRaises(AssertionError):
            self.loan_simulation.add_debt(O)
        with self.assertRaises(AssertionError):
            self.loan_simulation.add_debt(-ONE)

        prev_cash = self.loan_simulation.current_cash
        amount1 = self.loan_simulation.loan_amount()
        amount2 = amount1 / TWO
        debt1 = self.loan_simulation.amount_to_debt(amount1)
        debt2 = self.loan_simulation.amount_to_debt(amount2)
        loan1 = Loan(amount1, debt1, self.loan_simulation.today)
        loan2 = Loan(amount2, debt2, self.loan_simulation.today + 1)

        self.assertDeepAlmostEqual(self.loan_simulation.ledger.active_loans, [])
        self.loan_simulation.add_debt(amount1)
        self.assertEqual(self.loan_simulation.current_cash, prev_cash + amount1)
        self.assertEqual(self.loan_simulation.ledger.get_num_loans(), 1)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.active_loans, [loan1])
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.loans_history, [loan1])
        self.loan_simulation.today += 1
        self.loan_simulation.add_debt(amount2)
        self.assertEqual(self.loan_simulation.ledger.total_credit(), amount1 + amount2)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.active_loans, [loan1, loan2])
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.loans_history, [loan1, loan2])
        self.assertEqual(self.loan_simulation.ledger.get_num_loans(), 2)

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
        self.assertEqual(self.loan_simulation.credit_needed(), inventory_cost - 1)

    def test_update_credit_new_credit(self):
        self.loan_simulation.current_repayment_rate = 0.1
        self.loan_simulation.calculate_amount = MagicMock(return_value=self.loan_simulation.loan_amount())
        self.loan_simulation.primary_approval_conditions = MagicMock(return_value=True)
        self.loan_simulation.default_repayment_rate = MagicMock(return_value=0.3)
        self.loan_simulation.add_debt = MagicMock()
        self.loan_simulation.update_credit()
        self.loan_simulation.add_debt.assert_called_with(self.loan_simulation.loan_amount())
        self.assertEqual(self.loan_simulation.current_repayment_rate, 0.3)

    def test_approved_amount(self):
        self.loan_simulation.loan_amount = MagicMock(return_value=ONE)
        self.loan_simulation.underwriting.approved = MagicMock(return_value=True)
        self.assertEqual(self.loan_simulation.approved_amount(), 1)
        self.loan_simulation.underwriting.approved = MagicMock(return_value=False)
        self.assertEqual(self.loan_simulation.approved_amount(), 0)

    def test_reference_conditions(self):
        self.loan_simulation.reference_loan = None
        self.context.loan_reference_type = LoanReferenceType.REVENUE_CAGR
        self.assertTrue(self.loan_simulation.reference_conditions())
        reference_loan = LoanSimulation(self.context, self.data_generator, self.merchant)
        self.loan_simulation.set_reference_loan(reference_loan)
        self.context.loan_reference_type = None
        self.assertTrue(self.loan_simulation.reference_conditions())
        self.context.loan_reference_type = LoanReferenceType.REVENUE_CAGR
        reference_loan.revenue_cagr = MagicMock(return_value=ONE)
        self.loan_simulation.revenue_cagr = MagicMock(return_value=O)
        self.assertTrue(self.loan_simulation.reference_conditions())
        self.loan_simulation.revenue_cagr = MagicMock(return_value=ONE)
        self.loan_simulation.loan_reference_diff.fast_diff = MagicMock(return_value=False)
        self.assertTrue(self.loan_simulation.reference_conditions())
        self.loan_simulation.loan_reference_diff.fast_diff = MagicMock(return_value=True)
        self.assertFalse(self.loan_simulation.reference_conditions())

    def test_primary_approval_conditions(self):
        self.loan_simulation.secondary_approval_conditions = MagicMock(return_value=True)
        self.loan_simulation.credit_needed = MagicMock(return_value=ONE)
        self.loan_simulation.reference_conditions = MagicMock(return_value=True)
        self.loan_simulation.merchant.is_suspended = MagicMock(return_value=False)
        self.loan_simulation.projected_lender_profit = MagicMock(return_value=ONE)
        self.assertTrue(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.secondary_approval_conditions = MagicMock(return_value=False)
        self.assertFalse(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.secondary_approval_conditions = MagicMock(return_value=True)
        self.loan_simulation.credit_needed = MagicMock(return_value=O)
        self.assertFalse(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.credit_needed = MagicMock(return_value=ONE)
        self.loan_simulation.reference_conditions = MagicMock(return_value=False)
        self.assertFalse(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.reference_conditions = MagicMock(return_value=True)
        self.loan_simulation.merchant.is_suspended = MagicMock(return_value=True)
        self.assertFalse(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.merchant.is_suspended = MagicMock(return_value=False)
        self.loan_simulation.projected_lender_profit = MagicMock(return_value=Dollar(-1))
        self.assertFalse(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.projected_lender_profit = MagicMock(return_value=ONE)

    def test_secondary_approval_conditions(self):
        self.loan_simulation.credit_needed = MagicMock(return_value=ONE)
        self.loan_simulation.reference_conditions = MagicMock(return_value=True)
        self.assertTrue(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertFalse(self.loan_simulation.primary_approval_conditions())
        self.loan_simulation.ledger.initiate_loan_repayment(
            self.loan_simulation.today, self.loan_simulation.ledger.outstanding_balance())
        self.assertTrue(self.loan_simulation.primary_approval_conditions())

    def test_calculate_amount(self):
        self.loan_simulation.approved_amount = MagicMock(return_value=ONE)
        self.context.loan_reference_type = None
        self.assertEqual(ONE, self.loan_simulation.calculate_amount())
        self.context.loan_reference_type = LoanReferenceType.TOTAL_INTEREST
        reference_loan = LoanSimulation(self.context, self.data_generator, self.merchant)
        self.loan_simulation.reference_loan = reference_loan
        self.assertEqual(O, self.loan_simulation.calculate_amount())
        reference_loan.total_interest = MagicMock(return_value=ONE)
        self.assertEqual(ONE, self.loan_simulation.calculate_amount())
        self.loan_simulation.total_interest = MagicMock(return_value=ONE)
        self.assertEqual(O, self.loan_simulation.calculate_amount())

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
            self.loan_simulation.ledger.cash_history, {self.loan_simulation.today: self.loan_simulation.initial_cash})
        self.loan_simulation.today += 1
        self.loan_simulation.current_cash = -1
        self.loan_simulation.simulate_day()
        self.loan_simulation.on_bankruptcy.assert_called()

    def test_simulate_sales(self):
        self.loan_simulation.marketplace_balance = 1
        self.loan_simulation.revenues_to_date = 2
        self.loan_simulation.simulate_sales()
        self.assertEqual(
            self.loan_simulation.marketplace_balance, 1 + self.merchant.gp_per_day(self.data_generator.start_date))
        self.assertEqual(
            self.loan_simulation.revenues_to_date, 2 + self.merchant.revenue_per_day(self.data_generator.start_date))

    def test_simulate_inventory_purchase(self):
        self.loan_simulation.current_cash = 2
        self.merchant.inventory_cost = MagicMock(return_value=ONE)
        self.loan_simulation.simulate_inventory_purchase()
        self.assertEqual(self.loan_simulation.current_cash, 2 - 1)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.cash_history, {self.data_generator.start_date: ONE})

    def test_marketplace_payout_bankruptcy(self):
        self.loan_simulation.today = self.context.marketplace_payment_cycle
        self.loan_simulation.marketplace_balance = 0
        self.loan_simulation.merchant.has_future_revenue = MagicMock(return_value=False)
        self.loan_simulation.on_bankruptcy = MagicMock()
        self.loan_simulation.marketplace_payout()
        self.loan_simulation.on_bankruptcy.assert_called()

    def test_marketplace_payout(self):
        self.loan_simulation.today = self.context.marketplace_payment_cycle + 1
        self.loan_simulation.loan_repayment = MagicMock()
        self.loan_simulation.marketplace_balance = 1
        self.loan_simulation.current_cash = 2
        self.loan_simulation.marketplace_payout()
        self.loan_simulation.loan_repayment.assert_not_called()
        self.assertEqual(self.loan_simulation.current_cash, 2)
        self.assertEqual(self.loan_simulation.marketplace_balance, 1)
        self.loan_simulation.today = self.context.marketplace_payment_cycle
        self.loan_simulation.marketplace_payout()
        self.loan_simulation.loan_repayment.assert_called()
        self.assertEqual(self.loan_simulation.current_cash, 2 + 1)
        self.assertEqual(self.loan_simulation.marketplace_balance, 0)
        self.assertDeepAlmostEqual(
            self.loan_simulation.ledger.cash_history,
            {self.data_generator.start_date: self.loan_simulation.initial_cash, self.loan_simulation.today: 3})

    def test_simulate(self):
        self.loan_simulation.calculate_results = MagicMock()
        self.loan_simulation.simulate_day = MagicMock()
        self.loan_simulation.simulate()
        self.loan_simulation.calculate_results.assert_called()
        self.assertEqual(self.loan_simulation.simulate_day.call_count, self.data_generator.simulated_duration)
        self.assertEqual(self.loan_simulation.today, self.data_generator.simulated_duration)

    def test_simulation_stopped(self):
        self.loan_simulation.simulate_day = MagicMock()
        self.loan_simulation.should_stop_simulation = MagicMock(side_effect=[False, True])
        self.loan_simulation.simulate()
        self.assertEqual(self.loan_simulation.simulate_day.call_count, 2)
        self.assertEqual(self.loan_simulation.today, 2)

    def test_should_stop_simulation(self):
        self.loan_simulation.bankruptcy_date = None
        self.loan_simulation.reference_conditions = MagicMock(return_value=True)
        self.loan_simulation.merchant.annual_top_line = MagicMock(return_value=self.context.max_merchant_top_line + 1)
        self.assertTrue(self.loan_simulation.should_stop_simulation())
        self.loan_simulation.merchant.annual_top_line = MagicMock(return_value=self.context.max_merchant_top_line - 1)
        self.loan_simulation.reference_conditions = MagicMock(return_value=False)
        self.assertTrue(self.loan_simulation.should_stop_simulation())
        self.loan_simulation.reference_conditions = MagicMock(return_value=True)
        self.loan_simulation.bankruptcy_date = ONE_INT
        self.assertTrue(self.loan_simulation.should_stop_simulation())
        self.loan_simulation.bankruptcy_date = None
        self.assertFalse(self.loan_simulation.should_stop_simulation())

    def test_simulate_not_random(self):
        self.data_generator.simulated_duration = Date(constants.YEAR)
        self.data_generator.normal_ratio = MagicMock(return_value=Ratio(1))
        self.data_generator.random = MagicMock(return_value=Float(1))
        self.loan_simulation.simulate()
        self.data_generator.normal_ratio.assert_not_called()
        self.data_generator.random.assert_not_called()

    def test_simulate_deterministic(self):
        self.data_generator.simulated_duration = Date(constants.YEAR)
        loan2 = deepcopy(self.loan_simulation)
        self.loan_simulation.simulate()
        loan2.simulate()
        for field in fields(self.loan_simulation.simulation_results):
            val1 = getattr(self.loan_simulation.simulation_results, field.name)
            val2 = getattr(loan2.simulation_results, field.name)
            if isinstance(val1, bool):
                self.assertEqual(val1, val2)
            self.assertEqual(val1, val2)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.cash_history, loan2.ledger.cash_history)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.repayments, loan2.ledger.repayments)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.active_loans, loan2.ledger.active_loans)

    def test_simulate_bankruptcy(self):
        self.loan_simulation.simulate_day = MagicMock()
        self.loan_simulation.calculate_results = MagicMock()
        self.loan_simulation.bankruptcy_date = True
        self.loan_simulation.simulate()
        self.assertEqual(self.loan_simulation.simulate_day.call_count, 1)
        self.assertEqual(self.loan_simulation.today, self.data_generator.start_date)

    def test_loan_repayment_empty_repayment(self):
        self.loan_simulation.simulate_sales()
        prev_cash = self.loan_simulation.initial_cash
        self.loan_simulation.loan_repayment()
        self.assertEqual(self.loan_simulation.current_cash, prev_cash)
        self.assertDeepAlmostEqual(self.loan_simulation.ledger.repayments, [])

    def test_loan_repayment(self):
        amount = self.loan_simulation.loan_amount()
        debt = self.loan_simulation.amount_to_debt(amount)
        loan = Loan(amount, debt, self.loan_simulation.today)
        self.loan_simulation.add_debt(amount)
        self.assertEqual(self.loan_simulation.ledger.active_loans, [loan])
        prev_cash = self.loan_simulation.current_cash
        self.loan_simulation.marketplace_balance = debt / self.loan_simulation.current_repayment_rate
        self.loan_simulation.loan_repayment()
        self.assertEqual(self.loan_simulation.current_cash, prev_cash - debt)
        self.assertEqual(self.loan_simulation.ledger.active_loans, [])
        self.assertEqual(self.loan_simulation.ledger.loans_history, [loan])
        self.assertEqual(self.loan_simulation.ledger.repayments, [Repayment(ONE_INT, debt, ONE_INT)])

    def test_on_bankruptcy(self):
        self.loan_simulation.today = randint(self.data_generator.start_date, self.data_generator.simulated_duration)
        self.loan_simulation.on_bankruptcy()
        self.assertEqual(self.loan_simulation.bankruptcy_date, self.loan_simulation.today)

    def test_calculate_results(self):
        self.loan_simulation.merchant.valuation = MagicMock(return_value=Float(0))
        self.loan_simulation.revenue_cagr = MagicMock(return_value=Float(1))
        self.loan_simulation.total_revenue = MagicMock(return_value=Float(1.1))
        self.loan_simulation.inventory_cagr = MagicMock(return_value=Float(2))
        self.loan_simulation.net_cashflow_cagr = MagicMock(return_value=Float(3))
        self.loan_simulation.valuation_cagr = MagicMock(return_value=Float(4))
        self.loan_simulation.lender_profit = MagicMock(return_value=Float(5))
        self.loan_simulation.ledger.total_credit = MagicMock(return_value=Float(6))
        self.loan_simulation.lender_profit_margin = MagicMock(return_value=Float(7))
        self.loan_simulation.total_interest = MagicMock(return_value=Float(8))
        self.loan_simulation.debt_to_valuation = MagicMock(return_value=Float(9))
        self.loan_simulation.effective_apr = MagicMock(return_value=Float(10))
        self.loan_simulation.calculate_bankruptcy_rate = MagicMock(return_value=Float(11))
        self.loan_simulation.calculate_hyper_growth_rate = MagicMock(return_value=Float(12))
        self.loan_simulation.calculate_duration_in_debt_rate = MagicMock(return_value=Float(13))
        self.loan_simulation.ledger.get_num_loans = MagicMock(return_value=Int(14))
        self.loan_simulation.calculate_results()
        self.assertEqual(
            self.loan_simulation.simulation_results, LoanSimulationResults(
                O, Float(1), Float(1.1), Float(2), Float(3), Float(4), Float(5), Float(6), Float(7), Float(8), Float(9),
                Float(10),
                Float(11), Float(12), Float(13), Int(14)))

    def test_calculate_bankruptcy_rate(self):
        self.loan_simulation.bankruptcy_date = None
        self.assertEqual(self.loan_simulation.calculate_bankruptcy_rate(), 0)
        self.loan_simulation.bankruptcy_date = self.data_generator.simulated_duration / 10 + \
                                               self.data_generator.start_date
        self.assertEqual(self.loan_simulation.calculate_bankruptcy_rate(), 0.9)
        self.loan_simulation.bankruptcy_date = self.data_generator.start_date
        self.assertEqual(self.loan_simulation.calculate_bankruptcy_rate(), 1)
        self.loan_simulation.bankruptcy_date = self.data_generator.simulated_duration
        self.assertEqual(
            self.loan_simulation.calculate_bankruptcy_rate(),
            1 / self.data_generator.simulated_duration)

    def test_net_cashflow(self):
        self.assertEqual(self.loan_simulation.net_cashflow(), self.loan_simulation.initial_cash)
        amount = ONE
        debt = self.loan_simulation.amount_to_debt(amount)
        self.loan_simulation.add_debt(amount)
        self.assertEqual(self.loan_simulation.net_cashflow(), self.loan_simulation.initial_cash + amount - debt)

    def test_valuation_cagr(self):
        self.loan_simulation.today = Date(constants.YEAR)
        self.merchant.valuation = MagicMock(side_effect=[1, 3])
        self.assertEqual(self.loan_simulation.valuation_cagr(), 2)

    def test_inventory_cagr(self):
        self.loan_simulation.today = Date(constants.YEAR)
        self.merchant.inventory_value = MagicMock(side_effect=[1, 3])
        self.assertEqual(self.loan_simulation.inventory_cagr(), 2)

    def test_net_cashflow_cagr(self):
        self.loan_simulation.today = Date(constants.YEAR)
        self.loan_simulation.current_cash = self.loan_simulation.initial_cash * 2
        self.assertEqual(self.loan_simulation.net_cashflow_cagr(), 1)

    def test_revenue_cagr(self):
        self.loan_simulation.today = Date(constants.YEAR)
        self.merchant.annual_top_line = MagicMock(side_effect=[ONE, Dollar(3)])
        self.loan_simulation.revenues_to_date = Dollar(3)
        self.assertEqual(self.loan_simulation.revenue_cagr(), 2)

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
        self.assertEqual(self.loan_simulation.loss(), self.loan_simulation.loan_amount())
        self.loan_simulation.repaid_debt = MagicMock(return_value=self.loan_simulation.loan_amount() + 1)
        self.assertEqual(self.loan_simulation.loss(), 0)

    def test_loss_non_default(self):
        self.loan_simulation.is_default = MagicMock(return_value=False)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.context.loan_duration = 1
        daily_repayment = self.merchant.annual_top_line(
            self.loan_simulation.today) * self.loan_simulation.current_repayment_rate / Date(constants.YEAR)
        self.assertEqual(
            self.loan_simulation.loss(), self.loan_simulation.loan_amount() - daily_repayment)

    def test_cost_of_capital(self):
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=O)
        self.loan_simulation.projected_amount_per_repayment = MagicMock(return_value=ONE)
        debt1 = TWO
        debt2 = ONE
        repaid1 = self.loan_simulation.debt_to_loan_amount(TWO)
        repaid2 = self.loan_simulation.debt_to_loan_amount(ONE)
        coc = [self.loan_simulation.calculate_cost_of_capital_rate(self.context.marketplace_payment_cycle * (i + 1)) for
            i in range(4)]

        # First debt
        self.loan_simulation.add_debt(self.loan_simulation.debt_to_loan_amount(debt1))
        self.assertEqual(self.loan_simulation.cost_of_capital(), repaid1 * Float.average(coc[:2]))
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=ONE)
        # Simulating repayment
        duration = Duration(constants.MONTH)
        self.loan_simulation.ledger.repayments.append(Repayment(ONE_INT, ONE, duration))
        self.assertEqual(
            self.loan_simulation.cost_of_capital(),
            repaid2 * coc[0] + repaid2 * self.loan_simulation.calculate_cost_of_capital_rate(duration))
        self.loan_simulation.ledger.repayments = []
        # Simulating faster repayment
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=O)
        self.loan_simulation.projected_amount_per_repayment = MagicMock(return_value=TWO)
        self.assertEqual(self.loan_simulation.cost_of_capital(), repaid1 * coc[0])
        self.loan_simulation.projected_amount_per_repayment = MagicMock(return_value=ONE)
        # Moving today forward
        self.loan_simulation.today += self.context.marketplace_payment_cycle
        self.assertEqual(self.loan_simulation.cost_of_capital(), repaid1 * Float.average(coc[1:3]))
        # Second debt
        self.loan_simulation.add_debt(self.loan_simulation.debt_to_loan_amount(debt2))
        self.assertEqual(self.loan_simulation.cost_of_capital(), repaid1 * coc[2] + repaid2 * coc[1])
        # Repaying debt in the future
        self.loan_simulation.today += self.context.marketplace_payment_cycle - 1
        self.loan_simulation.ledger.initiate_loan_repayment(
            self.loan_simulation.today, self.loan_simulation.ledger.outstanding_balance())
        self.assertEqual(self.loan_simulation.cost_of_capital(), repaid1 * coc[1] + repaid2 * coc[0])

    def test_repaid_debt(self):
        self.loan_simulation.total_debt = MagicMock(return_value=10)
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=Float(6))
        self.assertEqual(self.loan_simulation.repaid_debt(), 4)

    def test_projected_remaining_debt_non_default(self):
        self.loan_simulation.is_default = MagicMock(return_value=False)
        self.loan_simulation.remaining_duration = MagicMock(return_value=Duration(2))
        self.loan_simulation.merchant.annual_top_line = MagicMock(return_value=3 * Date(constants.YEAR))
        self.loan_simulation.current_repayment_rate = 4
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.max_debt() - 2 * 3 * 4)
        self.loan_simulation.ledger.initiate_loan_repayment(self.loan_simulation.today, ONE)
        self.assertEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.max_debt() - 1 - 2 * 3 * 4)

    def test_projected_remaining_debt_default(self):
        self.loan_simulation.is_default = MagicMock(return_value=True)
        self.assertEqual(self.loan_simulation.projected_remaining_debt(), 0)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.ledger.outstanding_balance())
        repaid = ONE
        self.loan_simulation.ledger.initiate_loan_repayment(self.loan_simulation.today, repaid)
        self.assertEqual(
            self.loan_simulation.projected_remaining_debt(), self.loan_simulation.max_debt() - repaid)

    def test_debt_to_valuation(self):
        self.merchant.valuation = MagicMock(return_value=Dollar(2))
        self.assertEqual(self.loan_simulation.debt_to_valuation(), 0)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.assertEqual(self.loan_simulation.debt_to_valuation(), self.loan_simulation.max_debt() / 2)

    def test_lender_profit(self):
        self.assertEqual(self.loan_simulation.lender_profit(), 0)
        self.loan_simulation.is_default = MagicMock(return_value=True)
        coc = ONE
        self.loan_simulation.cost_of_capital = MagicMock(return_value=coc)
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        prev_loss = self.loan_simulation.loss()
        prev_ops = self.loan_simulation.operating_costs()
        max_costs = prev_loss + coc + prev_ops + self.context.merchant_cost_of_acquisition
        self.assertEqual(self.loan_simulation.lender_profit(), -max_costs)
        repaid = Dollar(2)
        self.loan_simulation.ledger.initiate_loan_repayment(self.loan_simulation.today, repaid)
        new_loss = prev_loss - repaid
        new_revenue = self.loan_simulation.interest_from_amount(self.loan_simulation.debt_to_loan_amount(repaid))
        new_costs = new_loss + coc + self.context.merchant_cost_of_acquisition + prev_ops
        self.assertEqual(self.loan_simulation.lender_profit(), new_revenue - new_costs)

    def test_lender_profit_margin(self):
        self.loan_simulation.lender_profit = MagicMock(return_value=O)
        self.loan_simulation.ledger.total_credit = MagicMock(return_value=O)
        self.assertEqual(self.loan_simulation.lender_profit_margin(), O)
        self.loan_simulation.ledger.total_credit = MagicMock(return_value=ONE)
        self.assertEqual(self.loan_simulation.lender_profit_margin(), O)
        self.loan_simulation.lender_profit = MagicMock(return_value=Dollar(-1))
        self.assertEqual(self.loan_simulation.lender_profit_margin(), O)
        self.loan_simulation.lender_profit = MagicMock(return_value=Dollar(0.5))
        self.assertEqual(self.loan_simulation.lender_profit_margin(), Percent(0.5))
        with self.assertRaises(AssertionError):
            self.loan_simulation.lender_profit = MagicMock(return_value=TWO)
            self.loan_simulation.lender_profit_margin()

    def test_projected_lender_profit(self):
        onboarding_profit = self.loan_simulation.projected_lender_profit()
        for _ in range(self.context.expected_loans_per_year):
            self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
            self.loan_simulation.current_cash += self.loan_simulation.interest_from_amount(
                self.loan_simulation.loan_amount())
        self.assertEqual(
            (onboarding_profit + self.context.merchant_cost_of_acquisition) / self.context.expected_loans_per_year,
            self.loan_simulation.projected_lender_profit())
        self.loan_simulation.today += self.context.loan_duration - 1
        self.loan_simulation.ledger.initiate_loan_repayment(
            self.loan_simulation.today, self.loan_simulation.ledger.outstanding_balance())
        self.assertEqual(onboarding_profit, self.loan_simulation.lender_profit())

    def test_undo_active_loans(self):
        prev_cash = self.loan_simulation.current_cash
        self.loan_simulation.add_debt(self.loan_simulation.loan_amount())
        self.loan_simulation.undo_active_loans()
        self.assertEqual(self.loan_simulation.current_cash, prev_cash)
        self.assertEqual(self.loan_simulation.ledger.outstanding_balance(), O)
        self.assertEqual(self.loan_simulation.ledger.total_credit(), O)

    def test_calculate_apr(self):
        self.assertEqual(self.loan_simulation.calculate_apr(Date(constants.YEAR)), self.loan_simulation.flat_fee)
        self.assertEqual(
            self.loan_simulation.calculate_apr(Date(constants.YEAR) / 2), (self.loan_simulation.flat_fee + 1) ** 2 - 1)

    def test_average_apr(self):
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=O)
        self.loan_simulation.projected_amount_per_repayment = MagicMock(return_value=ONE)
        debt1 = TWO
        debt2 = ONE
        apr = [self.loan_simulation.calculate_apr(self.context.marketplace_payment_cycle * (i + 1)) for i in range(3)]
        self.loan_simulation.add_debt(self.loan_simulation.debt_to_loan_amount(debt1))
        self.assertEqual(self.loan_simulation.effective_apr(), Float.average(apr[:2]))
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=ONE)
        self.assertEqual(self.loan_simulation.effective_apr(), apr[0])
        self.loan_simulation.projected_remaining_debt = MagicMock(return_value=O)
        self.loan_simulation.projected_amount_per_repayment = MagicMock(return_value=TWO)
        self.assertEqual(self.loan_simulation.effective_apr(), apr[0])
        self.loan_simulation.projected_amount_per_repayment = MagicMock(return_value=ONE)
        self.loan_simulation.today += self.context.marketplace_payment_cycle
        self.assertEqual(self.loan_simulation.effective_apr(), Float.average(apr[1:3]))
        self.loan_simulation.add_debt(self.loan_simulation.debt_to_loan_amount(debt2))
        self.assertEqual(self.loan_simulation.effective_apr(), (2 * apr[2] + apr[1]) / 3)
        self.loan_simulation.today += self.context.marketplace_payment_cycle - 1
        self.loan_simulation.ledger.initiate_loan_repayment(
            self.loan_simulation.today, self.loan_simulation.ledger.outstanding_balance())
        self.assertEqual(self.loan_simulation.effective_apr(), (2 * apr[1] + apr[0]) / 3)


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
        self.assertEqual(self.loan.simulation_results.apr, 0)
        self.assertEqual(self.loan.simulation_results.debt_to_valuation, 0)
        self.assertEqual(self.loan.simulation_results.lender_profit, 0)

    def test_loan_amount(self):
        self.assertEqual(self.loan.loan_amount(), 0)

