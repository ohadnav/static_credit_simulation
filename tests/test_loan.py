import logging
import math
import sys
from copy import deepcopy
from dataclasses import fields
from random import uniform, randint
from unittest.mock import MagicMock

from autologging import TRACE

from common import constants
from common.context import DataGenerator, SimulationContext
from common.util import inverse_cagr
from finance.loan import Loan, LoanSimulationResults, NoCapitalLoan, LoanHistory
from seller.merchant import Merchant
from tests.util_test import BaseTestCase


class TestLoan(BaseTestCase):
    def setUp(self) -> None:
        super(TestLoan, self).setUp()
        self.data_generator.max_num_products = 4
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)

    def test_init(self):
        self.assertEqual(self.loan.outstanding_debt, 0)
        self.assertEqual(self.loan.total_credit, 0)
        self.assertEqual(self.loan.total_revenues, 0)
        self.assertIsNone(self.loan.current_loan_amount)
        self.assertIsNone(self.loan.current_loan_start_date)
        self.assertDictEqual(self.loan.cash_history, {self.loan.today: self.loan.initial_cash})
        self.assertListEqual(self.loan.loan_history, [])

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
        with self.assertRaises(AssertionError):
            self.loan.add_debt(0)
        with self.assertRaises(AssertionError):
            self.loan.add_debt(-1)

    def test_add_debt(self):
        prev_cash = self.loan.current_cash
        amount1 = uniform(1, self.loan.max_debt())
        amount2 = uniform(1, self.loan.max_debt())
        self.loan.add_debt(amount1)
        self.assertAlmostEqual(self.loan.current_cash, prev_cash + amount1)
        self.assertAlmostEqual(self.loan.outstanding_debt, amount1 * (1 + self.loan.interest))
        self.assertAlmostEqual(self.loan.outstanding_debt, self.loan.total_credit)
        self.assertEqual(self.loan.current_loan_start_date, self.loan.today)
        self.assertAlmostEqual(self.loan.current_loan_amount, amount1)
        self.loan.outstanding_debt = 0
        self.loan.today += 1
        self.loan.add_debt(amount2)
        self.assertAlmostEqual(self.loan.outstanding_debt, amount2 * (1 + self.loan.interest))
        self.assertAlmostEqual(self.loan.total_credit, (amount1 + amount2) * (1 + self.loan.interest))
        self.assertEqual(self.loan.current_loan_start_date, self.loan.today)
        self.assertAlmostEqual(self.loan.current_loan_amount, amount2)
        self.assertEqual(self.loan.current_loan_start_date, self.loan.today)

    def test_max_debt(self):
        self.assertGreater(self.loan.max_debt(), self.loan.loan_amount())

    def test_credit_needed(self):
        inventory_cost = uniform(1, 1000)
        self.loan.current_cash = inventory_cost
        self.merchant.max_cash_needed = MagicMock(return_value=inventory_cost)
        self.assertEqual(self.loan.credit_needed(), 0)
        self.loan.current_cash = 0
        self.assertEqual(self.loan.credit_needed(), inventory_cost)
        self.loan.current_cash = 1
        self.assertAlmostEqual(self.loan.credit_needed(), inventory_cost - 1)

    def test_update_credit_new_credit(self):
        self.loan.outstanding_debt = 0
        self.loan.current_repayment_rate = 0.1
        self.loan.credit_needed = MagicMock(return_value=self.loan.loan_amount())
        self.loan.approved_amount = MagicMock(return_value=self.loan.loan_amount())
        self.loan.default_repayment_rate = MagicMock(return_value=0.3)
        self.loan.add_debt = MagicMock()
        self.loan.update_credit()
        self.loan.add_debt.assert_called_with(self.loan.loan_amount())
        self.assertEqual(self.loan.current_repayment_rate, 0.3)
        self.loan.credit_needed = MagicMock(return_value=self.loan.loan_amount() / 2 - 1)
        self.loan.update_credit()
        self.loan.add_debt.assert_called_with(self.loan.loan_amount() / 2)

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

    def test_simulate_day(self):
        self.loan.update_credit = MagicMock()
        self.loan.simulate_sales = MagicMock()
        self.loan.simulate_inventory_purchase = MagicMock()
        self.loan.marketplace_payout = MagicMock()
        self.loan.on_bankruptcy = MagicMock()
        self.loan.current_cash = 1
        self.loan.simulate_day()
        self.loan.update_credit.assert_called()
        self.loan.simulate_sales.assert_called()
        self.loan.simulate_inventory_purchase.assert_called()
        self.loan.marketplace_payout.assert_called()
        self.loan.on_bankruptcy.assert_not_called()
        self.assertDictEqual(self.loan.cash_history, {self.loan.today: self.loan.initial_cash})
        self.loan.today += 1
        self.loan.current_cash = -1
        self.loan.simulate_day()
        self.loan.on_bankruptcy.assert_called()

    def test_simulate_sales(self):
        self.loan.marketplace_balance = 1
        self.loan.total_revenues = 2
        self.loan.simulate_sales()
        self.assertAlmostEqual(self.loan.marketplace_balance, 1 + self.merchant.gp_per_day(constants.START_DATE))
        self.assertAlmostEqual(self.loan.total_revenues, 2 + self.merchant.revenue_per_day(constants.START_DATE))

    def test_simulate_inventory_purchase(self):
        self.loan.current_cash = 2
        self.merchant.inventory_cost = MagicMock(return_value=1)
        self.loan.simulate_inventory_purchase()
        self.assertEqual(self.loan.current_cash, 2 - 1)
        self.assertDictEqual(self.loan.cash_history, {constants.START_DATE: 1})

    def test_marketplace_payout_bankruptcy(self):
        self.loan.today = constants.MARKETPLACE_PAYMENT_CYCLE
        self.loan.marketplace_balance = 0
        self.loan.merchant.has_future_revenue = MagicMock(return_value=False)
        self.loan.on_bankruptcy = MagicMock()
        self.loan.marketplace_payout()
        self.loan.on_bankruptcy.assert_called()

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
        self.assertDictEqual(self.loan.cash_history, {constants.START_DATE: self.loan.initial_cash, self.loan.today: 3})

    def test_simulate(self):
        self.loan.calculate_results = MagicMock()
        self.loan.simulate_day = MagicMock()
        self.loan.simulate()
        self.loan.calculate_results.assert_called()
        self.assertEqual(self.loan.simulate_day.call_count, self.data_generator.simulated_duration)
        self.assertEqual(self.loan.today, self.data_generator.simulated_duration)

    def test_simulate_not_random(self):
        self.data_generator.simulated_duration = constants.YEAR
        self.data_generator.normal_ratio = MagicMock(return_value=1)
        self.data_generator.random = MagicMock(return_value=1)
        self.loan.simulate()
        self.data_generator.normal_ratio.assert_not_called()
        self.data_generator.random.assert_not_called()

    def test_simulate_deterministic(self):
        self.data_generator.simulated_duration = constants.YEAR
        loan2 = deepcopy(self.loan)
        self.loan.simulate()
        loan2.simulate()
        for field in fields(self.loan.simulation_results):
            val1 = getattr(self.loan.simulation_results, field.name)
            val2 = getattr(loan2.simulation_results, field.name)
            if isinstance(val1, bool):
                self.assertEqual(val1, val2)
            self.assertAlmostEqual(val1, val2)
        for day in self.loan.cash_history.keys():
            self.assertAlmostEqual(self.loan.cash_history[day], loan2.cash_history[day])

    def test_simulate_bankruptcy(self):
        self.loan.simulate_day = MagicMock()
        self.loan.calculate_results = MagicMock()
        self.loan.bankruptcy_date = True
        self.loan.simulate()
        self.assertEqual(self.loan.simulate_day.call_count, 1)
        self.assertEqual(self.loan.today, constants.START_DATE)

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
        self.loan.current_loan_duration = MagicMock(return_value=1)
        self.loan.add_debt(1)
        self.loan.close_loan()
        self.assertListEqual(self.loan.loan_history, [LoanHistory(1, 1)])
        self.assertIsNone(self.loan.current_loan_amount)
        self.assertIsNone(self.loan.current_loan_start_date)
        self.loan.add_debt(1)
        self.loan.current_loan_duration = MagicMock(return_value=2)
        self.loan.close_loan()
        self.assertListEqual(self.loan.loan_history, [LoanHistory(1, 1), LoanHistory(1, 2)])

    def test_on_bankruptcy(self):
        self.loan.today = randint(constants.START_DATE, self.data_generator.simulated_duration)
        self.loan.on_bankruptcy()
        self.assertEqual(self.loan.bankruptcy_date, self.loan.today)

    def test_calculate_results(self):
        self.loan.merchant.valuation = MagicMock(return_value=0)
        self.loan.revenue_cagr = MagicMock(return_value=1)
        self.loan.inventory_cagr = MagicMock(return_value=2)
        self.loan.net_cashflow_cagr = MagicMock(return_value=3)
        self.loan.valuation_cagr = MagicMock(return_value=4)
        self.loan.lender_profit = MagicMock(return_value=5)
        self.loan.debt_to_loan_amount = MagicMock(return_value=6)
        self.loan.debt_to_valuation = MagicMock(return_value=7)
        self.loan.average_apr = MagicMock(return_value=8)
        self.loan.calculate_bankruptcy_rate = MagicMock(return_value=9)
        self.loan.calculate_results()
        self.assertEqual(self.loan.simulation_results, LoanSimulationResults(0, 1, 2, 3, 4, 5, 6, 7, 8, 9))

    def test_calculate_bankruptcy_rate(self):
        self.loan.bankruptcy_date = None
        self.assertEqual(self.loan.calculate_bankruptcy_rate(), 0)
        self.loan.bankruptcy_date = self.data_generator.simulated_duration / 10 + constants.START_DATE
        self.assertEqual(self.loan.calculate_bankruptcy_rate(), 0.9)
        self.loan.bankruptcy_date = constants.START_DATE
        self.assertAlmostEqual(self.loan.calculate_bankruptcy_rate(), 1)
        self.loan.bankruptcy_date = self.data_generator.simulated_duration
        self.assertAlmostEqual(
            self.loan.calculate_bankruptcy_rate(),
            1 / self.data_generator.simulated_duration)

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
        self.loan.total_revenues = 1.5
        self.assertAlmostEqual(self.loan.revenue_cagr(), 0.5)

    def test_is_default(self):
        self.assertFalse(self.loan.is_default())
        self.loan.on_bankruptcy()
        self.assertTrue(self.loan.is_default())
        self.loan.bankruptcy_date = None
        self.context.duration_based_default = True
        self.loan.add_debt(1)
        self.assertFalse(self.loan.is_default())
        self.loan.today = self.context.loan_duration + 1
        self.assertTrue(self.loan.is_default())
        self.context.duration_based_default = False
        self.assertFalse(self.loan.is_default())

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
            self.loan.loss(), self.loan.loan_amount() - self.merchant.annual_top_line(
                self.loan.today) * self.loan.current_repayment_rate / constants.YEAR)

    def test_current_loan_duration(self):
        with self.assertRaises(AssertionError):
            self.loan.current_loan_duration()
        self.loan.add_debt(1)
        with self.assertRaises(AssertionError):
            self.loan.today -= 1
            self.loan.current_loan_duration()
        self.loan.today = constants.MARKETPLACE_PAYMENT_CYCLE
        self.assertEqual(self.loan.current_loan_duration(), self.context.loan_duration)
        self.loan.outstanding_debt = 0
        self.assertEqual(self.loan.current_loan_duration(), constants.MARKETPLACE_PAYMENT_CYCLE)
        self.loan.outstanding_debt = 1
        self.loan.marketplace_balance = 100000
        self.loan.marketplace_payout()
        with self.assertRaises(AssertionError):
            self.loan.current_loan_duration()
        self.loan.add_debt(1)
        self.assertEqual(self.loan.current_loan_duration(), self.context.loan_duration)
        self.loan.today += self.context.loan_duration
        self.assertEqual(self.loan.current_loan_duration(), self.context.loan_duration + 1)

    def test_cost_of_capital(self):
        self.loan.loan_amount = MagicMock(return_value=10)
        self.loan.add_debt(self.loan.loan_amount())
        actual_coc_rate = inverse_cagr(self.context.cost_of_capital, self.context.loan_duration)
        self.assertAlmostEqual(self.loan.cost_of_capital(), actual_coc_rate * self.loan.loan_amount())
        self.loan.today = self.context.loan_duration
        self.loan.simulate_sales()
        self.loan.marketplace_payout()
        self.assertAlmostEqual(self.loan.cost_of_capital(), actual_coc_rate * self.loan.loan_amount())
        self.loan.add_debt(self.loan.loan_amount())
        self.loan.today += constants.YEAR - 1
        self.loan.close_loan()
        self.assertAlmostEqual(
            self.loan.cost_of_capital(),
            actual_coc_rate * self.loan.loan_amount() + self.loan.loan_amount() * self.context.cost_of_capital)

    def test_projected_remaining_debt(self):
        self.loan.add_debt(self.loan.loan_amount())
        self.loan.is_default = MagicMock(return_value=False)
        self.assertAlmostEqual(
            self.loan.projected_remaining_debt(), max(
                0, self.loan.max_debt() - self.merchant.annual_top_line(
                    constants.START_DATE) * (
                           self.context.loan_duration / constants.YEAR) * self.loan.current_repayment_rate))
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
            prev_profit + 2 * (1 + self.loan.average_apr()))

    def test_projected_lender_profit(self):
        self.loan.loan_amount = MagicMock(return_value=10)
        self.loan.calculate_apr = MagicMock(return_value=0.1)
        self.context.merchant_cost_of_acquisition = 1
        self.context.cost_of_capital = 0.5
        self.context.loan_duration = 60
        self.context.expected_loans_per_year = 6
        projected_costs = 1 + 10 * inverse_cagr(0.5, 60) * 6
        projected_revenues = 10 * 0.1 * 6
        self.assertAlmostEqual(self.loan.projected_lender_profit(), projected_revenues - projected_costs)
        self.loan.total_credit = 1
        self.assertAlmostEqual(
            self.loan.projected_lender_profit(),
            projected_revenues - projected_costs + self.context.merchant_cost_of_acquisition)

    def test_apr(self):
        apr1 = self.loan.interest
        apr2 = math.pow(1 + self.loan.interest, 2) - 1
        self.loan.loan_history = [LoanHistory(10, constants.YEAR)]
        self.assertAlmostEqual(self.loan.average_apr(), apr1)
        self.loan.current_loan_start_date = constants.START_DATE
        self.loan.today = constants.START_DATE + constants.YEAR / 2 - 1
        self.loan.outstanding_debt = 1
        self.loan.current_loan_amount = 5
        self.assertAlmostEqual(self.loan.average_apr(), (2 * apr1 + apr2) / 3)


class TestNoCapitalLoan(BaseTestCase):
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
        self.data_generator.num_products = 2
        self.data_generator.max_num_products = 5
        self.context = SimulationContext()
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = NoCapitalLoan(self.context, self.data_generator, self.merchant)

    def test_add_debt(self):
        prev_cash = self.loan.current_cash
        amount1 = uniform(1, self.loan.max_debt())
        self.loan.add_debt(amount1)
        self.assertDictEqual(self.loan.cash_history, {self.loan.today: self.loan.current_cash})
        self.assertAlmostEqual(self.loan.current_cash, prev_cash)
        self.assertAlmostEqual(self.loan.outstanding_debt, 0)
        self.assertAlmostEqual(self.loan.total_credit, 0)
        self.assertIsNone(self.loan.current_loan_start_date)
        self.assertIsNone(self.loan.current_loan_amount)

    def test_simulate(self):
        self.loan.simulate()
        self.assertAlmostEqual(self.loan.outstanding_debt, 0)
        self.assertAlmostEqual(self.loan.total_credit, 0)
        self.assertAlmostEqual(self.loan.simulation_results.apr, 0)
        self.assertAlmostEqual(self.loan.simulation_results.debt_to_valuation, 0)
        self.assertAlmostEqual(self.loan.simulation_results.lender_profit, 0)

    def test_loan_amount(self):
        self.assertEqual(self.loan.loan_amount(), 0)
