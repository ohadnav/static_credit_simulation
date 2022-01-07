import logging
import sys
from copy import deepcopy
from typing import List, Tuple, Any, Union
from unittest import TestCase
from unittest.mock import MagicMock

from tqdm import tqdm

from common import constants
from common.constants import LoanType
from common.context import DataGenerator, SimulationContext
from finance.lender import Lender
from finance.line_of_credit import LineOfCredit, DynamicLineOfCredit
from finance.loan import Loan, NoCapitalLoan
from finance.underwriting import Underwriting
from seller.merchant import Merchant
from statistical_tests.statistical_test import statistical_test_bool, statistical_test_frequency


class TestStatisticalFinance(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=logging.INFO if sys.gettrace() else logging.WARNING, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()
        self.context = SimulationContext()
        self.data_generator.num_products = min(self.data_generator.num_products, self.data_generator.max_num_products)

    @statistical_test_bool(confidence=0.6)
    def test_big_merchants_profitable(self, is_true: List[List[Union[bool, Tuple[bool, Any]]]]):
        self.data_generator.min_purchase_order_value = 100000
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 3
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_true[0].append(self.loan.projected_lender_profit() > 0)

    @statistical_test_bool(confidence=0.6)
    def test_small_merchants_not_profitable(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.min_purchase_order_value = 1000
        self.data_generator.max_num_products = 5
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_true[0].append((self.loan.projected_lender_profit() < 0, round(self.loan.projected_lender_profit())))

    @statistical_test_frequency(frequency=0.2, margin=0.5)
    def test_some_sellers_approved_from_the_get_go(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        is_true[0].append(
            (self.loan.underwriting.approved(constants.START_DATE), round(self.loan.underwriting.aggregated_score())))

    @statistical_test_frequency(frequency=0.5, margin=0.5)
    def test_sellers_take_credit(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 2
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_true[0].append((self.loan.total_debt > 0, self.loan))

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

    @statistical_test_bool(confidence=0.52, times=100)
    def test_line_of_credit_more_efficient(self, is_true: List[List[Tuple[bool, Any]]]):
        self.context.merchant_cost_of_acquisition = 0
        self.data_generator.num_products = 2
        self.data_generator.max_num_products = 10
        line_of_credit = None
        regular_loan = None
        diff = False
        while not diff:
            merchant = Merchant.generate_simulated(self.data_generator)
            regular_loan = Loan(self.context, self.data_generator, deepcopy(merchant))
            line_of_credit = LineOfCredit(self.context, self.data_generator, merchant)
            line_of_credit.simulate()
            if line_of_credit.total_debt > 0:
                regular_loan.simulate()
                diff = line_of_credit.simulation_results != regular_loan.simulation_results
        regular_loan.simulate()
        is_true[0].append(
            (
                line_of_credit.simulation_results.valuation_cagr >
                regular_loan.simulation_results.valuation_cagr,
                (round(
                    line_of_credit.simulation_results.valuation_cagr -
                    regular_loan.simulation_results.valuation_cagr,
                    2), line_of_credit, regular_loan)))

    @statistical_test_bool(confidence=0.52, times=100)
    def test_dynamic_line_of_credit_more_profitable(self, is_true: List[List[Tuple[bool, Any]]]):
        self.context.merchant_cost_of_acquisition = 0
        self.data_generator.num_products = 2
        self.data_generator.max_num_products = 10
        line_of_credit = None
        dynamic_line_of_credit = None
        diff = False
        while not diff:
            merchant = Merchant.generate_simulated(self.data_generator)
            dynamic_line_of_credit = DynamicLineOfCredit(self.context, self.data_generator, deepcopy(merchant))
            line_of_credit = LineOfCredit(self.context, self.data_generator, merchant)
            line_of_credit.simulate()
            if line_of_credit.total_debt > 0:
                dynamic_line_of_credit.simulate()
                diff = line_of_credit.simulation_results != dynamic_line_of_credit.simulation_results
        is_true[0].append(
            (
                line_of_credit.simulation_results.lender_profit <
                dynamic_line_of_credit.simulation_results.lender_profit,
                (round(
                    dynamic_line_of_credit.simulation_results.lender_profit -
                    line_of_credit.simulation_results.lender_profit,
                    2), line_of_credit, dynamic_line_of_credit)))

    def test_dynamic_line_of_credit_improves_growth(self):
        dynamic_context = SimulationContext(LoanType.DYNAMIC_LINE_OF_CREDIT)
        dynamic_context.merchant_cost_of_acquisition = 0
        regular_context = SimulationContext(LoanType.FLAT_FEE)
        regular_context.merchant_cost_of_acquisition = 0
        merchants = []
        num_merchants = 1000
        with tqdm(total=num_merchants) as pbar:
            while len(merchants) < num_merchants:
                merchant = Merchant.generate_simulated(self.data_generator)
                regular_loan = Loan(self.context, self.data_generator, deepcopy(merchant))
                dloc = DynamicLineOfCredit(self.context, self.data_generator, merchant)
                dloc.simulate()
                regular_loan.simulate()
                diff = dloc.simulation_results != regular_loan.simulation_results
                if dloc.total_debt > 0:
                    if diff:
                        merchants.append(merchant)
                        pbar.update(1)
        regular_lender = Lender(regular_context, self.data_generator, merchants)
        dynamic_lender = Lender(dynamic_context, self.data_generator, deepcopy(merchants))
        regular_lender.simulate()
        dynamic_lender.simulate()
        print('regular: ' + str(regular_lender.simulation_results))
        print('dynamic: ' + str(dynamic_lender.simulation_results))
        self.assertNotEqual(regular_lender.simulation_results, dynamic_lender.simulation_results)
        self.assertLess(
            regular_lender.simulation_results.lender_gross_profit,
            dynamic_lender.simulation_results.lender_gross_profit)
        self.assertLess(regular_lender.simulation_results.sharpe, dynamic_lender.simulation_results.sharpe)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.valuation_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.valuation_cagr)

    @statistical_test_bool(confidence=0.6, num_lists=3, times=200)
    def test_funded_merchants_grow_faster(self, is_true: List[List[Tuple[bool, Any]]]):
        self.data_generator.num_products = 2
        self.data_generator.max_num_products = 10
        loan_with_capital = None
        loan_without_capital = None
        with_funds = False
        while not with_funds:
            merchant = Merchant.generate_simulated(self.data_generator)
            loan_without_capital = NoCapitalLoan(self.context, self.data_generator, deepcopy(merchant))
            loan_with_capital = Loan(self.context, self.data_generator, merchant)
            loan_with_capital.simulate()
            with_funds = loan_with_capital.total_debt > 0
        loan_without_capital.simulate()
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
                loan_with_capital.simulation_results.valuation_cagr >
                loan_without_capital.simulation_results.valuation_cagr,
                (round(
                    loan_with_capital.simulation_results.valuation_cagr -
                    loan_without_capital.simulation_results.valuation_cagr,
                    2), loan_with_capital, loan_without_capital)))
        is_true[2].append(
            (
                loan_with_capital.simulation_results.bankruptcy_rate <
                loan_without_capital.simulation_results.bankruptcy_rate,
                (round(
                    loan_without_capital.simulation_results.bankruptcy_rate -
                    loan_with_capital.simulation_results.bankruptcy_rate,
                    2), loan_with_capital, loan_without_capital)))

    @statistical_test_bool(confidence=0.5, num_lists=3)
    def test_merchants_growth_without_capital(self, is_true: List[List[Tuple[bool, Any]]]):
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = NoCapitalLoan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_true[0].append(
            not self.loan.bankruptcy_date or
            (-0.5 < self.loan.simulation_results.revenues_cagr < 2,
            (self.loan.simulation_results.revenues_cagr, self.loan)))
        is_true[1].append(
            not self.loan.bankruptcy_date or
            (-0.5 < self.loan.simulation_results.valuation_cagr < 2,
            (self.loan.simulation_results.valuation_cagr, self.loan)))
        is_true[2].append(
            not self.loan.bankruptcy_date or
            (-0.5 < self.loan.simulation_results.inventory_cagr < 2,
            (self.loan.simulation_results.inventory_cagr, self.loan)))

    @statistical_test_frequency(frequency=0.6)
    def test_merchants_bankruptcy_rates(self, is_true: List[List[Tuple[bool, Any]]]):
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = NoCapitalLoan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_true[0].append((self.loan.simulation_results.bankruptcy_rate < 0.5, self.loan))

    @statistical_test_frequency(frequency=0.8)
    def test_merchants_bankruptcy_rates_with_capital(self, is_true: List[List[Tuple[bool, Any]]]):
        self.merchant = Merchant.generate_simulated(self.data_generator)
        self.loan = Loan(self.context, self.data_generator, self.merchant)
        self.loan.simulate()
        is_true[0].append((self.loan.simulation_results.bankruptcy_rate < 0.5, self.loan))

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
