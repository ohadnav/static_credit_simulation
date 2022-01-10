from dataclasses import dataclass
from typing import Optional

from numpy.random import mtrand

from common import constants
from common.constants import LoanType
from common.util import Percent


@dataclass
class DataGenerator:
    randomness = True
    simulated_duration = constants.SIMULATION_DURATION
    num_merchants = constants.NUM_SIMULATED_MERCHANTS
    num_products = constants.NUM_PRODUCTS
    max_num_products = constants.MAX_NUM_PRODUCTS

    # Costs
    min_purchase_order_value = constants.MIN_PURCHASE_ORDER_VALUE
    shipping_duration_avg = constants.SHIPPING_DURATION_AVG
    shipping_duration_std = constants.SHIPPING_DURATION_STD
    manufacturing_duration_avg = constants.MANUFACTURING_DURATION_AVG
    manufacturing_duration_std = constants.MANUFACTURING_DURATION_STD
    sgna_ratio = constants.SGNA_RATIO_MIN
    inventory_cost_std = constants.INVENTORY_COST_STD
    out_of_stock_rate_median = constants.OUT_OF_STOCK_RATE_MEDIAN
    out_of_stock_rate_std = constants.OUT_OF_STOCK_RATE_STD
    cogs_margin_median = constants.COGS_MARGIN_BENCHMARK_AVG
    cogs_margin_std = constants.COGS_MARGIN_STD
    inventory_turnover_ratio_median = constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG
    inventory_turnover_ratio_std = constants.INVENTORY_TURNOVER_RATIO_STD
    include_purchase_order_in_valuation = True
    conservative_cash_management = True

    # Revenue
    initial_cash_ratio = constants.INITIAL_CASH_RATIO
    initial_stock_std = constants.INITIAL_STOCK_STD
    median_price = constants.MEDIAN_PRICE
    price_std = constants.PRICE_STD
    marketplace_payment_cycle = constants.MARKETPLACE_PAYMENT_CYCLE
    roas_std = constants.ROAS_STD
    organic_rate_std = constants.ORGANIC_RATE_STD
    roas_median = constants.ROAS_MEDIAN
    organic_rate_median = constants.ORGANIC_SALES_RATIO_MEDIAN

    # Fraud
    account_suspension_duration = constants.ACCOUNT_SUSPENSION_DURATION
    account_suspension_chance = constants.ACCOUNT_SUSPENSION_CHANCE

    def random(self) -> Percent:
        if self.randomness:
            return mtrand.random()
        return constants.NO_VOLATILITY

    def normal_ratio(self, std: float = 0.5, chance_positive: Percent = 0.5, max_ratio: float = 3) -> float:
        if self.randomness:
            positive = mtrand.random() < chance_positive
            random_value = abs(mtrand.normal(scale=std))
            random_value = min(max_ratio * std, random_value)
            return 1 + random_value if positive else 1 / (1 + random_value)
        return constants.NO_VOLATILITY

    def remove_randomness(self):
        self.randomness = False


@dataclass
class RiskConfiguration:
    higher_is_better: bool = True
    weight: float = constants.DEFAULT_RISK_PREDICTOR_WEIGHT
    threshold: Percent = constants.DEFAULT_RISK_MIN_THRESHOLD
    score: Optional[Percent] = None


class RiskContext:
    def __init__(self):
        self.out_of_stock_rate = RiskConfiguration(higher_is_better=False)
        self.inventory_turnover_ratio = RiskConfiguration()
        self.adjusted_profit_margin = RiskConfiguration()
        self.roas = RiskConfiguration()
        self.organic_rate = RiskConfiguration()


@dataclass
class SimulationContext:
    # Loan
    loan_type: LoanType = LoanType.DEFAULT
    rbf_flat_fee = constants.RBF_FLAT_FEE
    loan_duration = constants.LOAN_DURATION
    loan_amount_per_monthly_income = constants.LOAN_AMOUNT_PER_MONTHLY_INCOME
    delayed_loan_repayment_increase = constants.DELAYED_LOAN_REPAYMENT_INCREASE

    # Lender
    cost_of_capital = constants.COST_OF_CAPITAL
    expected_apr = constants.EXPECTED_APR
    merchant_cost_of_acquisition = constants.MERCHANT_COST_OF_ACQUISITION
    revenue_collateralization = False
    duration_based_default = False
    risk_context = RiskContext()
    expected_loans_per_year = constants.EXPECTED_LOANS_PER_YEAR

    # Underwriting
    organic_rate_benchmark = constants.ORGANIC_SALES_RATIO_MEDIAN
    out_of_stock_rate_benchmark = constants.OUT_OF_STOCK_RATE_MEDIAN
    adjusted_profit_margin_benchmark = constants.PROFIT_MARGIN_ADJUSTMENT
    inventory_turnover_ratio_benchmark = constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG
    roas_benchmark = constants.ROAS_MEDIAN
    benchmark_factor = constants.BENCHMARK_FACTOR
    min_risk_score = constants.MIN_RISK_SCORE
