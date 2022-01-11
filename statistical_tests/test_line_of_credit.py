from copy import deepcopy

from common.constants import LoanType
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
                factory.generate_lsr_validator(
                    [MerchantCondition('total_credit', loan_type=LoanType.LINE_OF_CREDIT, min_value=0),
                        MerchantCondition('bankruptcy_rate', loan_type=LoanType.NO_CAPITAL, max_value=0.01)]),
                num_merchants=1)
            lsr = results[0][1]
            loan_with_capital = lsr[0]
            loan_without_capital = lsr[1]
            is_true.append(
                (
                    loan_with_capital.revenues_cagr > loan_without_capital.revenues_cagr,
                    (round(
                        loan_with_capital.revenues_cagr - loan_without_capital.revenues_cagr, 2), lsr)))
            is_true.append(
                (
                    loan_with_capital.lender_profit > 0,
                    (round(loan_with_capital.lender_profit), loan_with_capital)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.6)

    def test_line_of_credit_superior(self):
        loc_context = SimulationContext(LoanType.LINE_OF_CREDIT)
        regular_context = SimulationContext(LoanType.FLAT_FEE)
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [MerchantCondition('total_credit', LoanType.DEFAULT, 1),
                    MerchantCondition(loan_type=LoanType.LINE_OF_CREDIT)]))
        merchants = [mnr[0] for mnr in merchants_and_results]
        regular_lender = Lender(regular_context, self.data_generator, merchants)
        loc_lender = Lender(loc_context, self.data_generator, deepcopy(merchants))
        regular_lender.simulate()
        loc_lender.simulate()
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
        dynamic_context = SimulationContext(LoanType.DYNAMIC_LINE_OF_CREDIT)
        loc_context = SimulationContext(LoanType.LINE_OF_CREDIT)
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [MerchantCondition('total_credit', LoanType.LINE_OF_CREDIT, 1),
                    MerchantCondition(loan_type=LoanType.DYNAMIC_LINE_OF_CREDIT)]))
        merchants = [mnr[0] for mnr in merchants_and_results]
        loc_lender = Lender(loc_context, self.data_generator, merchants)
        dynamic_lender = Lender(dynamic_context, self.data_generator, deepcopy(merchants))
        loc_lender.simulate()
        dynamic_lender.simulate()
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
            loc_lender.simulation_results.portfolio_merchants.net_cashflow_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.net_cashflow_cagr)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.revenues_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.revenues_cagr)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.apr,
            dynamic_lender.simulation_results.portfolio_merchants.apr)
        self.assertLess(
            loc_lender.simulation_results.portfolio_merchants.total_credit,
            dynamic_lender.simulation_results.portfolio_merchants.total_credit)
        self.assertGreaterEqual(
            loc_lender.simulation_results.portfolio_merchants.bankruptcy_rate,
            dynamic_lender.simulation_results.portfolio_merchants.bankruptcy_rate)
