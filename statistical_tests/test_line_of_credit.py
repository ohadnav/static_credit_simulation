from copy import deepcopy

from common.constants import LoanType
from common.context import SimulationContext, DataGenerator
from finance.lender import Lender
from simulation.merchant_factory import MerchantFactory, MerchantCondition
from statistical_tests.statistical_test import statistical_test_bool
from tests.util_test import StatisticalTestCase


class TestStatisticalFinance(StatisticalTestCase):
    def test_line_of_credit_more_efficient(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            is_true = []
            merchant_and_results = factory.generate_merchants(
                factory.generate_diff_validator(
                    [
                        MerchantCondition(loan_type=LoanType.DEFAULT),
                        MerchantCondition(loan_type=LoanType.LINE_OF_CREDIT)]), num_merchants=1)
            lsr = merchant_and_results[0][1]
            regular_loan = lsr[0]
            line_of_credit = lsr[1]
            is_true.append(
                (regular_loan.valuation_cagr < line_of_credit.valuation_cagr,
                (round(regular_loan.valuation_cagr - line_of_credit.valuation_cagr, 2), lsr)))
            is_true.append(
                (regular_loan.total_credit < line_of_credit.total_credit,
                (round(regular_loan.total_credit - line_of_credit.total_credit, 2), lsr)))
            is_true.append(
                (regular_loan.apr < line_of_credit.apr, (round(regular_loan.apr - line_of_credit.apr, 2), lsr)))
            is_true.append(
                (regular_loan.lender_profit < line_of_credit.lender_profit,
                (round(regular_loan.lender_profit - line_of_credit.lender_profit, 2), lsr)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.6)

    def test_dynamic_line_of_credit_superior(self):
        dynamic_context = SimulationContext(LoanType.DYNAMIC_LINE_OF_CREDIT)
        regular_context = SimulationContext(LoanType.FLAT_FEE)
        merchants_and_results = self.factory.generate_merchants(
            self.factory.generate_diff_validator(
                [MerchantCondition(loan_type=LoanType.DEFAULT),
                    MerchantCondition(loan_type=LoanType.DYNAMIC_LINE_OF_CREDIT)]))
        merchants = [mnr[0] for mnr in merchants_and_results]
        regular_lender = Lender(regular_context, self.data_generator, merchants)
        dynamic_lender = Lender(dynamic_context, self.data_generator, deepcopy(merchants))
        regular_lender.simulate()
        dynamic_lender.simulate()
        print(regular_lender.simulation_results)
        print(dynamic_lender.simulation_results)
        self.assertNotEqual(regular_lender.simulation_results, dynamic_lender.simulation_results)
        self.assertLess(
            regular_lender.simulation_results.lender_profit,
            dynamic_lender.simulation_results.lender_profit)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.valuation_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.valuation_cagr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.net_cashflow_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.net_cashflow_cagr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.revenues_cagr,
            dynamic_lender.simulation_results.portfolio_merchants.revenues_cagr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.apr,
            dynamic_lender.simulation_results.portfolio_merchants.apr)
        self.assertLess(
            regular_lender.simulation_results.portfolio_merchants.total_credit,
            dynamic_lender.simulation_results.portfolio_merchants.total_credit)
        self.assertGreaterEqual(
            regular_lender.simulation_results.portfolio_merchants.bankruptcy_rate,
            dynamic_lender.simulation_results.portfolio_merchants.bankruptcy_rate)
