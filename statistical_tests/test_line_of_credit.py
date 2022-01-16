from common.constants import LoanSimulationType
from common.context import SimulationContext, DataGenerator
from finance.lender import Lender
from simulation.merchant_factory import MerchantFactory, MerchantCondition
from statistical_tests.statistical_test import statistical_test_bool
from tests.util_test import StatisticalTestCase


class TestStatisticalLineOfCredit(StatisticalTestCase):
    def test_funded_merchants_grow_faster(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            is_true = []
            data_generator.num_products = 2
            data_generator.max_num_products = 10
            results = factory.generate_merchants(
                factory.generate_diff_validator(
                    [MerchantCondition(loan_type=LoanSimulationType.LINE_OF_CREDIT),
                        MerchantCondition(loan_type=LoanSimulationType.NO_CAPITAL)]),
                num_merchants=1)
            loans = results[0][1]
            loan_with_capital = loans[0].simulation_results
            loan_without_capital = loans[1].simulation_results
            is_true.append(
                (
                    loan_with_capital.revenues_cagr > loan_without_capital.revenues_cagr,
                    (
                        loan_with_capital.revenues_cagr - loan_without_capital.revenues_cagr, loans)))
            is_true.append(
                (
                    loan_with_capital.lender_profit > 0,
                    (loan_with_capital.lender_profit, loan_with_capital)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.6, times=50)

    def test_line_of_credit_superior(self):
        self.data_generator.num_merchants = 50
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [MerchantCondition(loan_type=LoanSimulationType.DEFAULT),
                    MerchantCondition(loan_type=LoanSimulationType.LINE_OF_CREDIT)]))
        regular_loans = [mnr[1][0] for mnr in merchants_and_results]
        loc_loans = [mnr[1][1] for mnr in merchants_and_results]
        regular_lender = Lender.generate_from_simulated_loans(regular_loans)
        loc_lender = Lender.generate_from_simulated_loans(loc_loans)
        print('results:')
        print(regular_lender.simulation_results)
        print(loc_lender.simulation_results)
        self.assertNotEqual(regular_lender.simulation_results, loc_lender.simulation_results)
        self.assertLess(
            regular_lender.simulation_results.lender_profit,
            loc_lender.simulation_results.lender_profit)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.valuation_cagr,
            loc_lender.simulation_results.portfolio_merchants.valuation_cagr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.net_cashflow_cagr,
            loc_lender.simulation_results.portfolio_merchants.net_cashflow_cagr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.revenues_cagr,
            loc_lender.simulation_results.portfolio_merchants.revenues_cagr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.apr,
            loc_lender.simulation_results.portfolio_merchants.apr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.total_credit,
            loc_lender.simulation_results.portfolio_merchants.total_credit)
        self.assertGreaterEqual(
            regular_lender.simulation_results.portfolio_merchants.bankruptcy_rate,
            loc_lender.simulation_results.portfolio_merchants.bankruptcy_rate)

    def test_dynamic_line_of_credit_superior(self):
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [MerchantCondition(loan_type=LoanSimulationType.LINE_OF_CREDIT),
                    MerchantCondition(loan_type=LoanSimulationType.DYNAMIC_LINE_OF_CREDIT)]))
        loc_loans = [mnr[1][0] for mnr in merchants_and_results]
        dynamic_loans = [mnr[1][1] for mnr in merchants_and_results]
        loc_lender = Lender.generate_from_simulated_loans(loc_loans)
        dynamic_lender = Lender.generate_from_simulated_loans(dynamic_loans)
        print(loc_lender.simulation_results)
        print(dynamic_lender.simulation_results)
        self.assertNotEqual(loc_lender.simulation_results, dynamic_lender.simulation_results)
        self.assertLess(
            loc_lender.simulation_results.lender_profit,
            dynamic_lender.simulation_results.lender_profit)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.valuation_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.valuation_cagr)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.revenues_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.revenues_cagr)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.apr,
            dynamic_lender.simulation_results.portfolio_merchants.apr)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.total_credit,
            dynamic_lender.simulation_results.portfolio_merchants.total_credit)
        self.assertLess(
            loc_lender.simulation_results.sharpe,
            dynamic_lender.simulation_results.sharpe)
        self.assertGreaterEqual(
            loc_lender.simulation_results.portfolio_merchants.bankruptcy_rate,
            dynamic_lender.simulation_results.portfolio_merchants.bankruptcy_rate)
