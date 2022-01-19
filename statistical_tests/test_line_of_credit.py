from common.context import SimulationContext, DataGenerator
from common.enum import LoanSimulationType, LoanReferenceType
from finance.lender import Lender
from finance.loan_simulation import LoanSimulation
from simulation.merchant_factory import MerchantFactory, Condition
from statistical_tests.statistical_util import statistical_test_bool, StatisticalTestCase, statistical_test_mean_error


class TestStatisticalLineOfCredit(StatisticalTestCase):
    def test_merchant_factory_reference_error(self):
        self.context.loan_reference_type = LoanReferenceType.EQUAL_GROWTH
        self.data_generator.num_merchants = 1
        condition1 = Condition(loan_type=LoanSimulationType.DEFAULT)
        condition2 = Condition(loan_type=LoanSimulationType.LINE_OF_CREDIT)

        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            merchant_and_results = factory.generate_from_conditions([condition1, condition2])
            loan1: LoanSimulation = merchant_and_results[0][1][0]
            loan2: LoanSimulation = merchant_and_results[0][1][1]
            return abs(loan1.revenue_cagr() / loan2.revenue_cagr() - 1)

        statistical_test_mean_error(self, test_iteration, times=10, mean_error=0.05)

    def test_funded_merchants_grow_faster(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            is_true = []
            data_generator.num_products = 2
            data_generator.max_num_products = 10
            results = factory.generate_merchants(
                factory.generate_diff_validator(
                    [Condition(loan_type=LoanSimulationType.LINE_OF_CREDIT),
                        Condition(loan_type=LoanSimulationType.NO_CAPITAL)]),
                num_merchants=1)
            loans = results[0][1]
            loan_with_capital = loans[0].simulation_results
            loan_without_capital = loans[1].simulation_results
            is_true.append((loan_with_capital.revenues_cagr > loan_without_capital.revenues_cagr, loans))
            is_true.append((loan_with_capital.bankruptcy_rate <= loan_without_capital.bankruptcy_rate, loans))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8, times=50)

    def test_line_of_credit_superior_when_controlling_growth_rates(self):
        self.context.loan_reference_type = LoanReferenceType.EQUAL_GROWTH
        self.data_generator.num_merchants = 10
        merchants_and_results = self.factory.generate_from_conditions(
            [Condition(loan_type=LoanSimulationType.DEFAULT),
                Condition(loan_type=LoanSimulationType.LINE_OF_CREDIT)])
        regular_loans = [mnr[1][0] for mnr in merchants_and_results]
        loc_loans = [mnr[1][1] for mnr in merchants_and_results]
        regular_lender = Lender.generate_from_simulated_loans(regular_loans)
        loc_lender = Lender.generate_from_simulated_loans(loc_loans)
        print('results:')
        print(regular_lender.simulation_results)
        print(loc_lender.simulation_results)
        self.assertNotEqual(regular_lender.simulation_results, loc_lender.simulation_results)
        self.assertLess(
            regular_lender.simulation_results.funded.lender_profit_margin /
            loc_lender.simulation_results.funded.lender_profit_margin - 1, 0.05)
        self.assertLess(
            regular_lender.simulation_results.funded.num_loans,
            loc_lender.simulation_results.funded.num_loans)
        self.assertGreater(
            regular_lender.simulation_results.funded.total_interest,
            loc_lender.simulation_results.funded.total_interest)
        self.assertGreater(
            regular_lender.simulation_results.funded.total_credit,
            loc_lender.simulation_results.funded.total_credit)
        self.assertGreater(
            regular_lender.simulation_results.funded.lender_profit,
            loc_lender.simulation_results.funded.lender_profit)
        self.assertGreater(
            regular_lender.simulation_results.funded.apr,
            loc_lender.simulation_results.funded.apr)
        self.assertGreater(
            regular_lender.simulation_results.funded.total_credit,
            loc_lender.simulation_results.funded.total_credit)
        self.assertGreaterEqual(
            regular_lender.simulation_results.funded.bankruptcy_rate,
            loc_lender.simulation_results.funded.bankruptcy_rate)

    def test_line_of_credit_superior(self):
        self.context.loan_reference_type = None
        self.data_generator.num_merchants = 50
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [Condition(loan_type=LoanSimulationType.DEFAULT),
                    Condition(loan_type=LoanSimulationType.LINE_OF_CREDIT)]))
        regular_loans = [mnr[1][0] for mnr in merchants_and_results]
        loc_loans = [mnr[1][1] for mnr in merchants_and_results]
        regular_lender = Lender.generate_from_simulated_loans(regular_loans)
        loc_lender = Lender.generate_from_simulated_loans(loc_loans)
        print('results:')
        print(regular_lender.simulation_results)
        print(loc_lender.simulation_results)
        self.assertNotEqual(regular_lender.simulation_results, loc_lender.simulation_results)
        self.assertLess(
            regular_lender.simulation_results.funded.lender_profit,
            loc_lender.simulation_results.funded.lender_profit)
        self.assertLess(
            regular_lender.simulation_results.funded.valuation_cagr,
            loc_lender.simulation_results.funded.valuation_cagr)
        self.assertLess(
            regular_lender.simulation_results.funded.net_cashflow_cagr,
            loc_lender.simulation_results.funded.net_cashflow_cagr)
        self.assertLess(
            regular_lender.simulation_results.funded.revenues_cagr,
            loc_lender.simulation_results.funded.revenues_cagr)
        self.assertLess(
            regular_lender.simulation_results.funded.total_credit,
            loc_lender.simulation_results.funded.total_credit)
        self.assertGreater(
            regular_lender.simulation_results.funded.apr,
            loc_lender.simulation_results.funded.apr)
        self.assertGreater(
            regular_lender.simulation_results.funded.num_loans,
            loc_lender.simulation_results.funded.num_loans)
        self.assertGreaterEqual(
            regular_lender.simulation_results.funded.bankruptcy_rate,
            loc_lender.simulation_results.funded.bankruptcy_rate)

    def test_dynamic_line_of_credit_superior(self):
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [Condition(loan_type=LoanSimulationType.LINE_OF_CREDIT),
                    Condition(loan_type=LoanSimulationType.DYNAMIC_LINE_OF_CREDIT)]))
        loc_loans = [mnr[1][0] for mnr in merchants_and_results]
        dynamic_loans = [mnr[1][1] for mnr in merchants_and_results]
        loc_lender = Lender.generate_from_simulated_loans(loc_loans)
        dynamic_lender = Lender.generate_from_simulated_loans(dynamic_loans)
        print(loc_lender.simulation_results)
        print(dynamic_lender.simulation_results)
        self.assertNotEqual(loc_lender.simulation_results, dynamic_lender.simulation_results)
        self.assertLess(
            loc_lender.simulation_results.funded.lender_profit,
            dynamic_lender.simulation_results.funded.lender_profit)
        self.assertLess(
            loc_lender.simulation_results.funded.total_credit,
            dynamic_lender.simulation_results.funded.total_credit)
