from copy import deepcopy

from common import constants
from common.constants import LoanSimulationType
from common.context import DataGenerator, SimulationContext
from common.util import O
from finance.line_of_credit import LineOfCreditSimulation
from finance.loan_simulation import LoanSimulation, NoCapitalLoanSimulation
from seller.merchant import Merchant
from simulation.merchant_factory import MerchantFactory, MerchantCondition
from statistical_tests.statistical_test import statistical_test_bool
from tests.util_test import StatisticalTestCase

OUT_DIR = '../out/'


class TestStatisticalLoan(StatisticalTestCase):
    def setUp(self) -> None:
        super(TestStatisticalLoan, self).setUp()
        self.data_generator.max_num_products = 10
        self.data_generator.num_products = 3

    def test_big_merchants_loans_profitable(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            data_generator.min_purchase_order_value = 100000
            merchant = Merchant.generate_simulated(data_generator)
            loan = LoanSimulation(context, data_generator, merchant)
            is_true.append((loan.projected_lender_profit() > 0, round(loan.projected_lender_profit())))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.6)

    def test_small_merchants_loans_not_profitable(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            data_generator.min_purchase_order_value = 1000
            merchant = Merchant.generate_simulated(data_generator)
            loan = LoanSimulation(context, data_generator, merchant)
            is_true.append((loan.projected_lender_profit() < 0, round(loan.projected_lender_profit())))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.25)

    def test_some_sellers_approved_from_the_get_go(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            merchant = Merchant.generate_simulated(data_generator)
            loan = LoanSimulation(context, data_generator, merchant)
            risk_dict = loan.underwriting.initial_risk_context.score_dict()
            is_true.append(
                (loan.underwriting.approved(constants.START_DATE), min(risk_dict, key=risk_dict.get)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.3)

    def test_sellers_credit_profitable(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            merchant = Merchant.generate_simulated(data_generator)
            loan = LoanSimulation(context, data_generator, merchant)
            is_true.append((loan.projected_lender_profit() > 0, loan))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.5)

    def test_sellers_take_credit(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            merchant = Merchant.generate_simulated(data_generator)
            loan = LoanSimulation(context, data_generator, merchant)
            loan.simulate()
            is_true.append((loan.total_credit > 0, loan))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.2)

    def test_bankruptcy_rate(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            merchant = Merchant.generate_simulated(data_generator)
            loan = NoCapitalLoanSimulation(context, data_generator, merchant)
            loan.simulate()
            is_true.append((loan.simulation_results.bankruptcy_rate < 0.1, loan))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.5)

    def test_bankruptcy_rate_with_credit(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            is_true = []
            loan = factory.generate_merchants(
                factory.generate_lsr_validator(
                    MerchantCondition('total_credit', LoanSimulationType.DEFAULT, min_value=0)),
                num_merchants=1)[0][1]
            is_true.append((loan.simulation_results.bankruptcy_rate > 0.1, loan))
            return is_true

        statistical_test_bool(self, test_iteration, max_frequency=0.2)

    def test_non_bankrupt_sellers_take_credit(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            merchant = factory.generate_merchants(
                factory.generate_lsr_validator(
                    MerchantCondition('bankruptcy_rate', LoanSimulationType.NO_CAPITAL, max_value=0.01)),
                num_merchants=1)[0][0]
            is_true = []
            loan = LoanSimulation(context, data_generator, merchant)
            loan.simulate()
            is_true.append((loan.total_credit > 0, loan))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.3)

    def test_cost_of_acquisition_reduce_approval_rates(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            context2 = deepcopy(context)
            context2.merchant_cost_of_acquisition /= 2
            merchant = Merchant.generate_simulated(data_generator)
            loan = LoanSimulation(context, data_generator, merchant)
            loan2 = LoanSimulation(context2, data_generator, deepcopy(merchant))
            loan.simulate()
            loan2.simulate()
            only1 = loan.total_credit > 0 and loan2.total_credit == 0
            only2 = loan.total_credit == 0 and loan2.total_credit > 0
            is_true.append((not only1, merchant))
            is_true.append((not only2, merchant))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.9)

    def test_funded_merchants_grow_faster(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            is_true = []
            data_generator.conservative_cash_management = True
            results = factory.generate_merchants(
                factory.generate_diff_validator(
                    [MerchantCondition(loan_type=LoanSimulationType.DEFAULT),
                        MerchantCondition(loan_type=LoanSimulationType.NO_CAPITAL)]),
                num_merchants=1)
            loans = results[0][1]
            loan_with_capital = loans[0].simulation_results
            loan_without_capital = loans[1].simulation_results
            is_true.append((loan_with_capital.revenues_cagr > loan_without_capital.revenues_cagr, loans))
            is_true.append((loan_with_capital.bankruptcy_rate <= loan_without_capital.bankruptcy_rate, loans))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8)

    def test_loans_profitable(self):
        def test_iteration(
                data_generator: DataGenerator, context: SimulationContext, factory: MerchantFactory, *args, **kwargs):
            is_true = []
            data_generator.conservative_cash_management = True
            results = factory.generate_merchants(
                factory.generate_lsr_validator(MerchantCondition('total_credit', LoanSimulationType.DEFAULT, O)),
                num_merchants=1)
            loan = results[0][1]
            is_true.append((loan.simulation_results.lender_profit > 0, loan))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.8)

    def test_merchants_grow_without_capital(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            is_true = []
            merchant = Merchant.generate_simulated(data_generator)
            loan = NoCapitalLoanSimulation(context, data_generator, merchant)
            loan.simulate()
            bankruptcy_or_negative_profits = not loan.bankruptcy_date or merchant.profit_margin(
                constants.START_DATE) < 0
            is_true.append(
                (
                    bankruptcy_or_negative_profits or
                    0 < loan.simulation_results.revenues_cagr,
                    (loan.simulation_results.revenues_cagr, loan)))
            is_true.append(
                (
                    bankruptcy_or_negative_profits or
                    0 < loan.simulation_results.valuation_cagr,
                    (loan.simulation_results.valuation_cagr, loan)))
            is_true.append(
                (
                    bankruptcy_or_negative_profits or
                    0 < loan.simulation_results.inventory_cagr,
                    (loan.simulation_results.inventory_cagr, loan)))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.5)

    def test_no_bankruptcy_with_unlimited_capital(self):
        def test_iteration(data_generator: DataGenerator, context: SimulationContext, *args, **kwargs):
            def always_approved(*args, **kwargs):
                return True

            is_true = []
            data_generator.conservative_cash_management = True
            merchant = Merchant.generate_simulated(data_generator)
            context.loan_amount_per_monthly_income = 100000
            loan = LineOfCreditSimulation(context, data_generator, merchant)
            loan.underwriting.approved = always_approved
            loan.simulate()
            is_true.append((loan.simulation_results.bankruptcy_rate < 0.01, loan))
            return is_true

        statistical_test_bool(self, test_iteration, min_frequency=0.99)
