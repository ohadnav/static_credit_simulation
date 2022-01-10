import logging
import sys
from copy import deepcopy
from typing import List, Tuple, Any, Union, Optional
from unittest import TestCase
from unittest.mock import MagicMock

from autologging import TRACE

from common import constants
from common.context import DataGenerator, SimulationContext
from finance.line_of_credit import LineOfCredit
from finance.loan import Loan, NoCapitalLoan
from finance.underwriting import Underwriting
from seller.merchant import Merchant
from statistical_tests.statistical_test import statistical_test_bool, statistical_test_frequency

OUT_DIR = '../out/'


class TestStatisticalFinance(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            # filename=f'{OUT_DIR}last_run_logging.log',
            # filemode='w',
            stream=sys.stderr,
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=TRACE if sys.gettrace() else logging.WARNING)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.context = SimulationContext()

    @statistical_test_bool(confidence=0.6)
    def test_big_merchants_loans_profitable(self, is_true: List[List[Union[bool, Tuple[bool, Any]]]]):
        self.data_generator.min_purchase_order_value = 100000
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 3
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_true[0].append(self.loan.projected_lender_profit() > 0)

    @statistical_test_bool(confidence=0.25)
    def test_small_merchants_loans_not_profitable(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.min_purchase_order_value = 1000
        self.data_generator.max_num_products = 5
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_true[0].append((self.loan.projected_lender_profit() < 0, round(self.loan.projected_lender_profit())))

    @statistical_test_bool(confidence=0.2)
    def test_some_sellers_approved_from_the_get_go(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_true[0].append(
            (self.loan.underwriting.approved(constants.START_DATE), round(self.loan.underwriting.aggregated_score())))

    @statistical_test_bool(confidence=0.2)
    def test_sellers_take_credit(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_true[0].append((self.loan.total_debt > 0, self.loan))

    @statistical_test_frequency(frequency=0.5, margin=0.8)
    def test_bankruptcy_rate(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = NoCapitalLoan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_true[0].append((self.loan.simulation_results.bankruptcy_rate < 0.1, self.loan))

    @statistical_test_bool(confidence=0.3)
    def test_non_bankrupt_sellers_take_credit(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        bankruptcy = True
        loan: Optional[Loan] = None
        no_capital_loan: Optional[NoCapitalLoan] = None
        while bankruptcy:
            merchant = Merchant.generate_simulated(self.data_generator)
            loan = Loan(self.context, self.data_generator, deepcopy(merchant))
            no_capital_loan = NoCapitalLoan(self.context, self.data_generator, merchant)
            no_capital_loan.simulate()
            bankruptcy = no_capital_loan.simulation_results.bankruptcy_rate > 0.1
        loan.simulate()
        is_true[0].append((loan.total_debt > 0, (loan, no_capital_loan)))

    @statistical_test_bool(confidence=0.9, num_lists=2)
    def test_cost_of_acquisition_reduce_approval_rates(self, is_true: List[List[Tuple[bool, Any]]]):
        context2 = deepcopy(self.context)
        context2.merchant_cost_of_acquisition = 0
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, merchant)
        loan2 = Loan(context2, self.data_generator, deepcopy(merchant))
        self.loan.simulate()
        loan2.simulate()
        only1 = self.loan.total_debt > 0 and loan2.total_debt == 0
        only2 = self.loan.total_debt == 0 and loan2.total_debt > 0
        is_true[0].append((not only1, merchant))
        is_true[1].append((not only2, merchant))

    @statistical_test_bool(confidence=0.6, num_lists=2, disable_tracing=False)
    def test_funded_merchants_grow_faster(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.num_products = 2
        self.data_generator.max_num_products = 10
        self.data_generator.conservative_cash_management = True
        loan_with_capital = None
        loan_without_capital = None
        bankrupt_or_no_credit = True
        while bankrupt_or_no_credit:
            merchant = Merchant.generate_simulated(self.data_generator)
            loan_without_capital = NoCapitalLoan(self.context, self.data_generator, deepcopy(merchant))
            loan_with_capital = Loan(self.context, self.data_generator, merchant)
            loan_with_capital.simulate()
            loan_without_capital.simulate()
            no_credit = loan_with_capital.total_debt < constants.FLOAT_ADJUSTMENT
            bankruptcy = loan_without_capital.simulation_results.bankruptcy_rate > 0.01
            bankrupt_or_no_credit = no_credit or bankruptcy
        is_true[0].append(
            (
                loan_with_capital.simulation_results.revenues_cagr >
                loan_without_capital.simulation_results.revenues_cagr,
                (round(
                    loan_with_capital.simulation_results.revenues_cagr -
                    loan_without_capital.simulation_results.revenues_cagr,
                    2), loan_with_capital, loan_without_capital)))
        is_true[1].append(
            (
                loan_with_capital.simulation_results.lender_profit > 0,
                (round(loan_with_capital.simulation_results.lender_profit), loan_with_capital, loan_without_capital)))

    @statistical_test_bool(confidence=0.5, num_lists=3)
    def test_merchants_grow_without_capital(self, is_true: List[List[Tuple[bool, Any]]]):
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = NoCapitalLoan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        bankruptcy_or_negative_profits = not self.loan.bankruptcy_date or self.merchant.profit_margin(
            constants.START_DATE) < 0
        is_true[0].append(
            bankruptcy_or_negative_profits or
            (0 < self.loan.simulation_results.revenues_cagr,
            (self.loan.simulation_results.revenues_cagr, self.loan)))
        is_true[1].append(
            bankruptcy_or_negative_profits or
            (0 < self.loan.simulation_results.valuation_cagr,
            (self.loan.simulation_results.valuation_cagr, self.loan)))
        is_true[2].append(
            bankruptcy_or_negative_profits or
            (0 < self.loan.simulation_results.inventory_cagr,
            (self.loan.simulation_results.inventory_cagr, self.loan)))

    @statistical_test_bool(confidence=0.99)
    def test_no_bankruptcy_with_unlimited_capital(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.conservative_cash_management = True
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.context.loan_amount_per_monthly_income = 100000
        self.loan = LineOfCredit(self.context, self.data_generator, self.merchant)
        self.loan.underwriting.approved = MagicMock(return_value=True)
        self.loan.simulate()
        is_true[0].append((self.loan.simulation_results.bankruptcy_rate < 0.01, self.loan))

    def test_risk_factors(self):
        for predictor, configuration in vars(self.context.risk_context).items():
            @statistical_test_bool(confidence=0.6)
            def test_factor(self, is_true: List[List[Union[bool, Tuple[bool, Any]]]]):
                merchant1 = Merchant.generate_simulated(self.data_generator)
                merchant2 = Merchant.generate_simulated(self.data_generator)
                benchmark = getattr(self.context, f'{predictor}_benchmark')
                setattr(merchant1, predictor, MagicMock(return_value=benchmark))
                setattr(
                    merchant2, predictor,
                    MagicMock(return_value=benchmark / 2 if configuration.higher_is_better else benchmark * 2))
                underwriting1 = Underwriting(self.context, merchant1)
                underwriting2 = Underwriting(self.context, merchant2)
                is_true[0].append(underwriting1.aggregated_score() > underwriting2.aggregated_score())

            test_factor(self)

