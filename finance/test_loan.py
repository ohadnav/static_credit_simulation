import logging
import sys
from random import uniform
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE, traced, logged

from common import constants
from common.context import DataGenerator, SimulationContext
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
            level=TRACE, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.context = SimulationContext()
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)

    def test_init(self):
        self.assertEqual(self.loan.outstanding_debt, 0)
        self.assertEqual(self.loan.total_debt, 0)

    def test_default_repayment_rate(self):
        self.assertAlmostEqual(self.loan.default_repayment_rate(), self.loan.max_debt()/self.loan.expected_revenue_during_loan())
        self.loan.max_debt = MagicMock(return_value=100000000)
        self.assertEqual(self.loan.default_repayment_rate(), constants.MAX_REPAYMENT_RATE)
        self.loan.max_debt = MagicMock(return_value=0)
        self.assertEqual(self.loan.default_repayment_rate(), constants.MIN_REPAYMENT_RATE)

    def test_expected_revenue_during_loan(self):
        self.context.loan_duration = constants.YEAR / 2
        self.assertAlmostEqual(self.loan.expected_revenue_during_loan(), self.merchant.annual_top_line(constants.START_DATE) * 0.5)

    def test_add_debt(self):
        prev_cash = self.loan.current_cash
        debt1 = uniform(1, self.loan.max_debt())
        debt2 = uniform(1, self.loan.max_debt())
        self.loan.add_debt(debt1)
        self.assertAlmostEqual(self.loan.current_cash, prev_cash + debt1)
        self.assertAlmostEqual(self.loan.outstanding_debt, debt1 * (1 + self.loan.fixed_interest()))
        self.assertAlmostEqual(self.loan.outstanding_debt, self.loan.total_debt)
        self.loan.outstanding_debt = 0
        self.loan.add_debt(debt2)
        self.assertAlmostEqual(self.loan.outstanding_debt, debt2 * (1 + self.loan.fixed_interest()))
        self.assertAlmostEqual(self.loan.total_debt, (debt1+debt2) * (1 + self.loan.fixed_interest()))

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
        self.assertEqual(self.loan.approved_amount(), 1)
        self.loan.underwriting.approved = MagicMock(return_value=False)
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
        self.assertEqual(self.loan.simulate_next_day.call_count, constants.SIMULATION_DURATION)
        self.assertEqual(self.loan.today, constants.SIMULATION_DURATION)

    def test_simulate_bankruptcy(self):
        self.loan.simulate_next_day = MagicMock()
        self.loan.calculate_results = MagicMock()
        self.loan.is_bankrupt = True
        self.loan.simulate()
        self.assertEqual(self.loan.simulate_next_day.call_count, 1)
        self.assertEqual(self.loan.today, 1)

    def test_loan_repayment(self):
        self.loan.current_cash = 2
        self.loan.outstanding_debt = 0
        self.loan.marketplace_balance = 1
        self.loan.calculate_repayment_rate = MagicMock(return_value=0.1)
        self.loan.loan_repayment()
        self.assertEqual(self.loan.current_cash, 2)
        self.loan.outstanding_debt = 1
        self.loan.loan_repayment()
        self.assertEqual(self.loan.current_cash, 1.9)
        self.assertEqual(self.loan.outstanding_debt, 0.9)
        self.loan.marketplace_balance = 10
        self.loan.loan_repayment()
        self.assertAlmostEqual(self.loan.current_cash, 1)
        self.assertEqual(self.loan.outstanding_debt, 0)

    def test_bankruptcy(self):
        self.loan.bankruptcy()
        self.assertTrue(self.loan.is_bankrupt)

    def test_calculate_results(self):
        self.loan.revenue_cagr = MagicMock(return_value=1)
        self.loan.inventory_cagr = MagicMock(return_value=2)
        self.loan.net_cashflow_cagr = MagicMock(return_value=3)
        self.loan.valuation_cagr = MagicMock(return_value=4)
        self.loan.lender_profit = MagicMock(return_value=5)
        self.loan.debt_to_valuation = MagicMock(return_value=6)
        self.loan.apr = MagicMock(return_value=7)
        self.assertEqual(self.loan.calculate_results(), LoanSimulationResults(1,2,3,4,5,6,7))

    def test_apr(self):
        self.fail()

    def test_valuation_cagr(self):
        self.fail()

    def test_inventory_cagr(self):
        self.fail()

    def test_net_cashflow_cagr(self):
        self.fail()

    def test_revenue_cagr(self):
        self.fail()

    def test_lender_profit(self):
        self.fail()
