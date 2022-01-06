import logging
import math
import sys
from random import uniform
from typing import List
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import traced, logged, TRACE

from common import constants
from common.context import DataGenerator, SimulationContext
from common.statistical_test import statistical_test_bigger
from finance.loan import Loan, LoanSimulationResults
from seller.merchant import Merchant


@traced
@logged
class TestLoan(TestCase):
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
        self.context = SimulationContext()
        self.data_generator.max_num_products = 2
        self.data_generator.num_products = min(self.data_generator.num_products, self.data_generator.max_num_products)
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)

    def test_init(self):
        self.assertEqual(self.loan.outstanding_debt, 0)
        self.assertEqual(self.loan.total_debt, 0)
        self.assertIsNone(self.loan.current_loan_amount)
        self.assertIsNone(self.loan.current_loan_start_date)

    def test_default_repayment_rate(self):
        self.assertAlmostEqual(
            self.loan.default_repayment_rate(), self.loan.max_debt() / self.loan.expected_revenue_during_loan())
        self.loan.max_debt = MagicMock(return_value=100000000)
        self.assertEqual(self.loan.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)
        self.loan.max_debt = MagicMock(return_value=0)
        self.assertEqual(self.loan.default_repayment_rate(), constants.MIN_REPAYMENT_RATE)
        self.loan.expected_revenue_during_loan = MagicMock(return_value=0)
        self.assertEqual(self.loan.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)

    def test_expected_revenue_during_loan(self):
        self.context.loan_duration = constants.YEAR / 2
        self.assertAlmostEqual(
            self.loan.expected_revenue_during_loan(),
            self.merchant.annual_top_line(constants.START_DATE) * 0.5)

    def test_add_debt_0_amount(self):
        self.loan.add_debt(0)
        self.assertEqual(self.loan.outstanding_debt, 0)
        self.assertEqual(self.loan.total_debt, 0)
        self.assertIsNone(self.loan.current_loan_start_date)
        self.assertIsNone(self.loan.current_loan_amount)

    def test_add_debt(self):
        prev_cash = self.loan.current_cash
        amount1 = uniform(1, self.loan.max_debt())
        amount2 = uniform(1, self.loan.max_debt())
        self.loan.add_debt(amount1)
        self.assertAlmostEqual(self.loan.current_cash, prev_cash + amount1)
        self.assertAlmostEqual(self.loan.outstanding_debt, amount1 * (1 + self.loan.interest))
        self.assertAlmostEqual(self.loan.outstanding_debt, self.loan.total_debt)
        self.assertEqual(self.loan.current_loan_start_date, self.loan.today)
        self.assertAlmostEqual(self.loan.current_loan_amount, amount1)
        self.loan.outstanding_debt = 0
        self.loan.add_debt(amount2)
        self.assertAlmostEqual(self.loan.outstanding_debt, amount2 * (1 + self.loan.interest))
        self.assertAlmostEqual(self.loan.total_debt, (amount1 + amount2) * (1 + self.loan.interest))
        self.assertEqual(self.loan.current_loan_start_date, self.loan.today)
        self.assertAlmostEqual(self.loan.current_loan_amount, amount1 + amount2)

    def test_max_debt(self):
        self.assertGreater(self.loan.max_debt(), self.loan.loan_amount())

    def test_credit_needed(self):
        inventory_cost = uniform(1, 1000)
        self.loan.current_cash = inventory_cost
        self.merchant.max_inventory_cost = MagicMock(return_value=inventory_cost)
        self.assertEqual(self.loan.credit_needed(), 0)
        self.loan.current_cash = 0
        self.assertEqual(self.loan.credit_needed(), inventory_cost)
        self.loan.current_cash = 1
        self.assertAlmostEqual(self.loan.credit_needed(), inventory_cost - 1)

    def test_update_credit_new_credit(self):
        self.loan.outstanding_debt = 0
        self.loan.current_repayment_rate = 0.1
        self.loan.credit_needed = MagicMock(return_value=1)
        self.loan.default_repayment_rate = MagicMock(return_value=0.3)
        self.loan.add_debt = MagicMock()
        self.loan.update_credit()
        self.loan.add_debt.assert_called()
        self.assertEqual(self.loan.current_repayment_rate, 0.3)

    def test_approved_amount(self):
        self.loan.loan_amount = MagicMock(return_value=1)
        self.loan.underwriting.approved = MagicMock(return_value=True)
        self.loan.projected_lender_profit = MagicMock(return_value=1)
        self.assertEqual(self.loan.approved_amount(), 1)
        self.loan.underwriting.approved = MagicMock(return_value=False)
        self.assertEqual(self.loan.approved_amount(), 0)
        self.loan.underwriting.approved = MagicMock(return_value=True)
        self.loan.projected_lender_profit = MagicMock(return_value=-1)
        self.assertEqual(self.loan.approved_amount(), 0)

    def test_simulate_next_day(self):
        self.loan.update_credit = MagicMock()
        self.loan.simulate_sales = MagicMock()
        self.loan.simulate_inventory_purchase = MagicMock()
        self.loan.marketplace_payout = MagicMock()
        self.loan.bankruptcy = MagicMock()
        self.loan.current_cash = 1
        self.loan.simulate_next_day()
        self.loan.update_credit.assert_called()
        self.loan.simulate_sales.assert_called()
        self.loan.simulate_inventory_purchase.assert_called()
        self.loan.marketplace_payout.assert_called()
        self.loan.bankruptcy.assert_not_called()
        self.loan.current_cash = -1
        self.loan.simulate_next_day()
        self.loan.bankruptcy.assert_called()

    def test_simulate_sales(self):
        self.loan.marketplace_balance = 1
        self.loan.simulate_sales()
        self.assertEqual(self.loan.marketplace_balance, 1 + self.merchant.gp_per_day(constants.START_DATE))

    def test_simulate_inventory_purchase(self):
        self.loan.current_cash = 2
        self.merchant.inventory_cost = MagicMock(return_value=1)
        self.loan.simulate_inventory_purchase()
        self.assertEqual(self.loan.current_cash, 2 - 1)

    def test_marketplace_payout(self):
        self.loan.today = constants.MARKETPLACE_PAYMENT_CYCLE + 1
        self.loan.loan_repayment = MagicMock()
        self.loan.marketplace_balance = 1
        self.loan.current_cash = 2
        self.loan.marketplace_payout()
        self.loan.loan_repayment.assert_not_called()
        self.assertEqual(self.loan.current_cash, 2)
        self.assertEqual(self.loan.marketplace_balance, 1)
        self.loan.today = constants.MARKETPLACE_PAYMENT_CYCLE
        self.loan.marketplace_payout()
        self.loan.loan_repayment.assert_called()
        self.assertEqual(self.loan.current_cash, 2 + 1)
        self.assertEqual(self.loan.marketplace_balance, 0)

    def test_simulate(self):
        self.loan.calculate_results = MagicMock()
        self.loan.simulate_next_day = MagicMock()
        self.loan.simulate()
        self.loan.calculate_results.assert_called()
        self.assertEqual(self.loan.simulate_next_day.call_count, self.data_generator.simulated_duration)
        self.assertEqual(self.loan.today, self.data_generator.simulated_duration + constants.START_DATE)

    def test_simulate_bankruptcy(self):
        self.loan.simulate_next_day = MagicMock()
        self.loan.calculate_results = MagicMock()
        self.loan.is_bankrupt = True
        self.loan.simulate()
        self.assertEqual(self.loan.simulate_next_day.call_count, 1)
        self.assertEqual(self.loan.today, 1 + constants.START_DATE)

    def test_loan_repayment(self):
        self.loan.close_loan = MagicMock()
        amount1 = uniform(1, self.loan.initial_cash)
        self.loan.outstanding_debt = 0
        self.loan.marketplace_balance = 1
        self.loan.current_repayment_rate = 0.1
        self.loan.loan_repayment()
        self.assertEqual(self.loan.current_cash, self.loan.initial_cash)
        self.loan.close_loan.assert_not_called()
        self.loan.outstanding_debt = amount1
        self.loan.loan_repayment()
        self.assertEqual(self.loan.current_cash, self.loan.initial_cash - 0.1)
        self.assertEqual(self.loan.outstanding_debt, amount1 - 0.1)
        self.loan.close_loan.assert_not_called()
        self.loan.marketplace_balance = amount1 * 10
        self.loan.loan_repayment()
        self.assertAlmostEqual(self.loan.current_cash, self.loan.initial_cash - amount1)
        self.assertEqual(self.loan.outstanding_debt, 0)
        self.loan.close_loan.assert_called()

    def test_close_loan(self):
        self.loan.current_loan_amount = 1
        self.loan.current_loan_start_date = constants.START_DATE
        apr1 = self.loan.current_loan_apr()
        self.loan.close_loan()
        self.assertListEqual(self.loan.amount_history, [1])
        self.assertListEqual(self.loan.apr_history, [apr1])
        self.assertIsNone(self.loan.current_loan_amount)
        self.assertIsNone(self.loan.current_loan_start_date)

    def test_current_loan_apr(self):
        self.loan.current_loan_start_date = constants.START_DATE
        self.context.loan_duration = constants.YEAR
        self.assertAlmostEqual(self.loan.current_loan_apr(), self.loan.interest)
        self.context.loan_duration = constants.YEAR / 2
        self.assertAlmostEqual(self.loan.current_loan_apr(), math.pow(1 + self.loan.interest, 2) - 1)
        self.loan.today = constants.YEAR
        self.assertAlmostEqual(self.loan.current_loan_apr(), self.loan.interest)

    def test_bankruptcy(self):
        self.loan.bankruptcy()
        self.assertTrue(self.loan.is_bankrupt)

    def test_calculate_results(self):
        self.loan.merchant.valuation = MagicMock(return_value=0)
        self.loan.revenue_cagr = MagicMock(return_value=1)
        self.loan.inventory_cagr = MagicMock(return_value=2)
        self.loan.net_cashflow_cagr = MagicMock(return_value=3)
        self.loan.valuation_cagr = MagicMock(return_value=4)
        self.loan.lender_profit = MagicMock(return_value=5)
        self.loan.debt_to_valuation = MagicMock(return_value=6)
        self.loan.average_apr = MagicMock(return_value=7)
        self.loan.calculate_results()
        self.assertEqual(self.loan.simulation_results, LoanSimulationResults(0, 1, 2, 3, 4, 5, 6, 7))

    def test_net_cashflow(self):
        self.loan.outstanding_debt = 1
        self.assertEqual(self.loan.net_cashflow(), self.loan.initial_cash - 1)
        self.loan.add_debt(1)
        self.assertEqual(self.loan.net_cashflow(), self.loan.initial_cash - 1 - self.loan.interest)

    def test_valuation_cagr(self):
        self.loan.today = constants.YEAR
        self.merchant.valuation = MagicMock(side_effect=[1, 3])
        self.assertAlmostEqual(self.loan.valuation_cagr(), 2)

    def test_inventory_cagr(self):
        self.loan.today = constants.YEAR
        self.merchant.inventory_value = MagicMock(side_effect=[1, 3])
        self.assertAlmostEqual(self.loan.inventory_cagr(), 2)

    def test_net_cashflow_cagr(self):
        self.loan.today = constants.YEAR
        self.loan.current_cash = self.loan.initial_cash * 2
        self.assertAlmostEqual(self.loan.net_cashflow_cagr(), 1)

    def test_revenue_cagr(self):
        self.loan.today = constants.YEAR
        self.merchant.annual_top_line = MagicMock(side_effect=[1, 3])
        self.assertAlmostEqual(self.loan.revenue_cagr(), 2)

    def test_is_default(self):
        self.assertFalse(self.loan.is_default())
        self.loan.bankruptcy()
        self.assertTrue(self.loan.is_default())
        self.loan.is_bankrupt = False
        self.loan.add_debt(1)
        self.assertFalse(self.loan.is_default())
        self.loan.today = self.context.loan_duration + 1
        self.assertTrue(self.loan.is_default())

    def test_loss_default(self):
        self.assertEqual(self.loan.loss(), 0)
        self.loan.add_debt(self.loan.loan_amount())
        self.loan.is_default = MagicMock(return_value=True)
        self.assertAlmostEqual(self.loan.loss(), self.loan.loan_amount())
        self.loan.outstanding_debt = self.loan.loan_amount() * self.loan.interest
        self.assertAlmostEqual(self.loan.loss(), 0)

    def test_loss_non_default(self):
        self.assertEqual(self.loan.loss(), 0)
        self.loan.add_debt(self.loan.loan_amount())
        self.loan.is_default = MagicMock(return_value=False)
        self.context.loan_duration = 1
        self.assertAlmostEqual(
            self.loan.loss(), self.loan.loan_amount() - self.merchant.revenue_per_day(
                self.loan.today) * self.loan.current_repayment_rate)

    def test_cost_of_capital(self):
        self.loan.add_debt(self.loan.loan_amount())
        self.assertAlmostEqual(self.loan.cost_of_capital(), self.context.cost_of_capital * self.loan.loan_amount())
        self.loan.simulate_sales()
        self.loan.marketplace_payout()
        self.assertAlmostEqual(self.loan.cost_of_capital(), self.context.cost_of_capital * self.loan.loan_amount())

    def test_projected_remaining_debt(self):
        self.loan.add_debt(self.loan.loan_amount())
        self.loan.is_default = MagicMock(return_value=False)
        self.assertAlmostEqual(
            self.loan.projected_remaining_debt(), max(
                0, self.loan.max_debt() - self.merchant.revenue_per_day(
                    constants.START_DATE) * self.context.loan_duration * self.loan.current_repayment_rate))
        self.loan.is_default = MagicMock(return_value=True)
        self.assertAlmostEqual(self.loan.projected_remaining_debt(), self.loan.max_debt())
        self.loan.outstanding_debt -= 1
        self.assertAlmostEqual(self.loan.projected_remaining_debt(), self.loan.max_debt() - 1)

    def test_debt_to_valuation(self):
        self.merchant.valuation = MagicMock(return_value=2)
        self.assertAlmostEqual(self.loan.debt_to_valuation(), 0)
        self.loan.add_debt(self.loan.loan_amount())
        self.assertAlmostEqual(self.loan.debt_to_valuation(), self.loan.max_debt() / 2)

    def test_lender_profit(self):
        self.assertEqual(self.loan.lender_profit(), 0)
        self.loan.is_default = MagicMock(return_value=True)
        self.loan.add_debt(self.loan.loan_amount())
        self.assertEqual(
            self.loan.lender_profit(),
            -(self.loan.loss() + self.loan.cost_of_capital() + self.context.merchant_cost_of_acquisition))
        prev_profit = self.loan.lender_profit()
        self.loan.outstanding_debt -= 2
        self.assertAlmostEqual(
            self.loan.lender_profit(),
            prev_profit + 2 * (1 + self.loan.interest))

    def test_projected_lender_profit(self):
        self.loan.underwriting.approved = MagicMock(return_value=False)
        self.assertEqual(self.loan.projected_lender_profit(), 0)
        self.loan.underwriting.approved = MagicMock(return_value=True)
        self.loan.loan_amount = MagicMock(return_value=10)
        self.context.merchant_cost_of_acquisition = 1
        self.context.cost_of_capital = 0.5
        self.loan.interest = 0.08
        self.context.expected_loans_per_year = 6
        projected_costs = 1 + 10 * 0.5
        projected_revenues = 10 * 0.08 * 6
        self.assertAlmostEqual(self.loan.projected_lender_profit(), projected_revenues - projected_costs)

    @statistical_test_bigger(confidence=0.6)
    def test_big_merchants_profitable(self, is_bigger: List[bool]):
        self.data_generator.min_purchase_order_value = 100000
        self.data_generator.num_products = 10
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_bigger.append(self.loan.projected_lender_profit() > 0)

    @statistical_test_bigger(confidence=0.6)
    def test_small_merchants_not_profitable(self, is_bigger: List[bool]):
        self.data_generator.min_purchase_order_value = 1000
        self.data_generator.max_num_products = 2
        self.data_generator.num_products = min(self.data_generator.num_products, self.data_generator.max_num_products)
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_bigger.append(self.loan.projected_lender_profit() < 0)

    @statistical_test_bigger(confidence=0.8, num_lists=4)
    def test_funded_merchants_profitable_and_growing(self, is_bigger: List[List[bool]]):
        self.data_generator.num_products = 10
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        while self.loan.projected_lender_profit() < 0:
            self.merchant = Merchant.generate_simulated(self.data_generator)
            self.loan = Loan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_bigger[0].append(self.loan.simulation_results.lender_profit > 0)
        is_bigger[0].append(self.loan.simulation_results.revenues_cagr > 0)
        is_bigger[0].append(self.loan.simulation_results.net_cashflow_cagr > 0)
        is_bigger[0].append(self.loan.simulation_results.valuation_cagr > 0)

    def test_apr(self):
        self.loan.apr_history = [0.5]
        self.loan.amount_history = [1]
        self.assertEqual(self.loan.average_apr(), 0.5)
        self.loan.current_loan_apr = MagicMock(return_value=0.1)
        self.loan.outstanding_debt = 1
        self.loan.current_loan_start_date = self.loan.today
        self.loan.current_loan_amount = 3
        self.assertEqual(self.loan.average_apr(), 0.2)
