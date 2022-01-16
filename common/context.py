from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Mapping

from numpy.random import mtrand

from common import constants
from common.constants import LoanSimulationType
from common.util import Percent, Float, Ratio, ONE


@dataclass(unsafe_hash=True)
class DataGenerator:
    randomness = True
    simulated_duration = constants.SIMULATION_DURATION
    num_merchants = constants.NUM_SIMULATED_MERCHANTS
    num_products = constants.NUM_PRODUCTS
    max_num_products = constants.MAX_NUM_PRODUCTS
    num_products_std = constants.NUM_PRODUCTS_STD

    # Costs
    # TODO: add data gen STD to diversify initial underwriting values
    min_purchase_order_value = constants.MIN_PURCHASE_ORDER_VALUE
    shipping_duration_avg = constants.SHIPPING_DURATION_AVG
    shipping_duration_std = constants.SHIPPING_DURATION_STD
    manufacturing_duration_avg = constants.MANUFACTURING_DURATION_AVG
    manufacturing_duration_std = constants.MANUFACTURING_DURATION_STD
    sgna_rate = constants.SGNA_RATE_MIN
    sgna_rate_std = constants.SGNA_RATE_STD
    inventory_cost_std = constants.INVENTORY_COST_STD
    out_of_stock_rate_median = constants.OUT_OF_STOCK_RATE_MEDIAN
    out_of_stock_rate_std = constants.OUT_OF_STOCK_RATE_STD
    cogs_margin_median = constants.COGS_MARGIN_MEDIAN
    cogs_margin_std = constants.COGS_MARGIN_STD
    inventory_turnover_ratio_median = constants.INVENTORY_TURNOVER_RATIO_MEDIAN
    inventory_turnover_ratio_std = constants.INVENTORY_TURNOVER_RATIO_STD
    include_purchase_order_in_valuation = True
    conservative_cash_management = True
    first_batch_std_factor = constants.FIRST_BATCH_STD_FACTOR

    # Revenue
    initial_cash_ratio = constants.INITIAL_CASH_RATIO
    initial_stock_std = constants.INITIAL_STOCK_STD
    median_price = constants.MEDIAN_PRICE
    price_std = constants.PRICE_STD
    marketplace_payment_cycle = constants.MARKETPLACE_PAYMENT_CYCLE
    roas_std = constants.ROAS_STD
    organic_rate_std = constants.ORGANIC_RATE_STD
    roas_median = constants.ROAS_MEDIAN
    organic_rate_median = constants.ORGANIC_SALES_RATE_MEDIAN

    # Fraud
    account_suspension_duration = constants.ACCOUNT_SUSPENSION_DURATION
    account_suspension_chance = constants.ACCOUNT_SUSPENSION_CHANCE

    @classmethod
    def generate_data_generator(cls) -> DataGenerator:
        data_generator = DataGenerator()
        for key in dir(data_generator):
            if not key.startswith('_'):
                value = getattr(data_generator, key)
                if isinstance(value, float):
                    setattr(data_generator, key, Float(value))
        return data_generator

    def random(self) -> Percent:
        if self.randomness:
            return Float(mtrand.random())
        return Float(constants.NO_VOLATILITY)

    def normal_ratio(self, std: float = 0.5, chance_positive: float = 0.5, max_ratio: float = 3) -> Ratio:
        if self.randomness:
            positive = mtrand.random() < chance_positive
            random_value = abs(mtrand.normal(scale=std))
            random_value = Float.min(max_ratio * std, random_value)
            ratio = ONE + random_value
            return ratio if positive else ONE / ratio
        return constants.NO_VOLATILITY

    def remove_randomness(self):
        self.randomness = False


@dataclass(unsafe_hash=True)
class RiskConfiguration:
    # TODO: consider adding noise per each check
    higher_is_better: bool = True
    weight: Float = Float(constants.DEFAULT_RISK_PREDICTOR_WEIGHT)
    threshold: Percent = Percent(constants.DEFAULT_RISK_MIN_THRESHOLD)
    sensitivity: Ratio = Ratio(constants.LOW_UNDERWRITING_SENSITIVITY)
    score: Optional[Percent] = None


class RiskContext:
    def __init__(self):
        self.out_of_stock_rate = RiskConfiguration(
            higher_is_better=False, sensitivity=constants.MEDIUM_UNDERWRITING_SENSITIVITY)
        self.inventory_turnover_ratio = RiskConfiguration(sensitivity=constants.MEDIUM_UNDERWRITING_SENSITIVITY)
        self.adjusted_profit_margin = RiskConfiguration()
        self.roas = RiskConfiguration(sensitivity=constants.HIGH_UNDERWRITING_SENSITIVITY)
        self.organic_rate = RiskConfiguration(sensitivity=constants.HIGH_UNDERWRITING_SENSITIVITY)

    def score_dict(self) -> Mapping[str, Percent]:
        sd = {k: v.score for k, v in vars(self).items()}
        return sd


@dataclass(unsafe_hash=True)
class SimulationContext:
    @classmethod
    def generate_context(cls, loan_type: LoanSimulationType = LoanSimulationType.DEFAULT) -> SimulationContext:
        context = SimulationContext()
        context.loan_type = loan_type
        for key in dir(context):
            if not key.startswith('_'):
                value = getattr(context, key)
                if isinstance(value, float):
                    setattr(context, key, Float(value))
        return context

    # Loan
    loan_type = LoanSimulationType.DEFAULT
    rbf_flat_fee = constants.RBF_FLAT_FEE
    loan_duration = constants.LOAN_DURATION
    loan_amount_per_monthly_income = constants.LOAN_AMOUNT_PER_MONTHLY_INCOME
    delayed_loan_repayment_increase = constants.DELAYED_LOAN_REPAYMENT_INCREASE
    repayment_factor = constants.REPAYMENT_FACTOR

    # Lender
    cost_of_capital = constants.COST_OF_CAPITAL
    merchant_cost_of_acquisition = constants.MERCHANT_COST_OF_ACQUISITION
    revenue_collateralization = True
    duration_based_default = False
    risk_context = RiskContext()
    expected_loans_per_year = constants.EXPECTED_LOANS_PER_YEAR

    # Underwriting
    organic_rate_benchmark = constants.ORGANIC_SALES_RATE_BENCHMARK
    out_of_stock_rate_benchmark = constants.OUT_OF_STOCK_RATE_BENCHMARK_MIN
    adjusted_profit_margin_benchmark = constants.PROFIT_MARGIN_BENCHMARK_MAX
    inventory_turnover_ratio_benchmark = constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX
    roas_benchmark = constants.ROAS_BENCHMARK_MAX
    min_risk_score = constants.MIN_RISK_SCORE
