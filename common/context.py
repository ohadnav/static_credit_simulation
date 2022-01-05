from dataclasses import dataclass, fields
from typing import Optional, Mapping

from numpy.random import mtrand

from common import constants
from common.constants import LoanType
from common.util import Percent, min_max


@dataclass
class DataGenerator:
    randomness = True

    # Costs
    num_products = 1
    shipping_duration_avg = constants.SHIPPING_DURATION_MIN
    shipping_duration_std = constants.SHIPPING_DURATION_MIN
    manufacturing_duration_avg = constants.MANUFACTURING_DURATION_MIN
    manufacturing_duration_std = constants.MANUFACTURING_DURATION_STD
    sgna_payment_cycle = constants.SGNA_PAYMENT_CYCLE
    sgna_std = constants.SGNA_STD
    sgna_ratio = constants.SGNA_RATIO_MIN
    inventory_cost_std = constants.INVENTORY_COST_STD
    out_of_stock_ratio_median = constants.OUT_OF_STOCK_BENCHMARK
    cogs_margin_median = constants.COGS_MARGIN_BENCHMARK_AVG
    inventory_turnover_ratio_median = constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG
    sgna_ratio_median = constants.SGNA_RATIO_MIN

    # Revenue
    initial_cash_ratio = constants.INITIAL_CASH_RATIO
    initial_cash_std = constants.INITIAL_CASH_STD
    median_price = constants.MEDIAN_PRICE
    price_std = constants.PRICE_STD
    organic_growth_rate = constants.ORGANIC_GROWTH_RATE
    organic_sales_cycle = constants.ORGANIC_SALES_CYCLE
    marketplace_payment_cycle = constants.MARKETPLACE_PAYMENT_CYCLE
    growth_rate_avg = constants.GROWTH_RATE_AVG
    sales_volatility_cycle = constants.SALES_VOLATILITY_CYCLE
    organic_sales_volatility = constants.ORGANIC_SALES_VOLATILITY
    roas_variance = constants.ROAS_VOLATILITY
    organic_ratio_variance = constants.ORGANIC_RATIO_VARIANCE
    cashflow_buffer_from_top_line = constants.CASHFLOW_BUFFER_FROM_TOP_LINE
    roas_median = constants.ROAS_BENCHMARK_MIN
    organic_ratio_median = constants.ORGANIC_SALES_RATIO_BENCHMARK_MIN
    revenue_variance = constants.AVERAGE_SALES_VOLATILITY

    # Fraud
    account_suspension_duration = constants.ACCOUNT_SUSPENSION_DURATION
    account_suspension_chance = constants.ACCOUNT_SUSPENSION_CHANCE

    def random(self) -> Percent:
        if self.randomness:
            return mtrand.random()
        return constants.NO_VOLATILITY

    def normal(self, mean: float = 0, std: float = 1, min_value: Optional[float] = None,
               max_value: Optional[float] = None) -> float:
        if self.randomness:
            random_value = mtrand.normal(mean, std)
            max_value = max_value or mean + constants.MAX_RANDOM_DEVIATION * std
            min_value = min_value or mean - constants.MAX_RANDOM_DEVIATION * std
            random_value = min_max(random_value, min_value, max_value)
            return random_value
        return mean

    def normal_ratio(self, std: float = 1, chance_positive: Percent = 0.5, max_ratio: float = 3) -> float:
        if self.randomness:
            positive = mtrand.random() < chance_positive
            random_value = abs(mtrand.normal(scale=std))
            random_value = min(max_ratio * std, random_value)
            return 1 + random_value if positive else 1 / (1 + random_value)
        return constants.NO_VOLATILITY

    def randint(self, _from: int, _to: int) -> int:
        if self.randomness:
            return mtrand.randint(_from, _to)
        return _from

    def remove_randomness(self):
        self.randomness = False


@dataclass
class RiskConfiguration:
    higher_is_better: bool = True
    weight: float = constants.DEFAULT_RISK_PREDICTOR_WEIGHT
    threshold: Percent = constants.DEFAULT_RISK_MIN_THRESHOLD
    score: Optional[Percent] = None


@dataclass
class RiskContext:
    out_of_stock_ratio = RiskConfiguration(higher_is_better=False)
    inventory_turnover_ratio = RiskConfiguration()
    total_revenue = RiskConfiguration()
    cogs_margin = RiskConfiguration(higher_is_better=False)
    roas = RiskConfiguration()
    organic_ratio = RiskConfiguration()
    debt_to_inventory = RiskConfiguration(higher_is_better=False)

    def to_dict(self) -> Mapping[str, RiskConfiguration]:
        result = {}
        for predictor in fields(self):
            risk_configuration: RiskConfiguration = getattr(self, predictor.name)
            result[predictor.name] = risk_configuration
        return result


@dataclass
class SimulationContext:
    loan_type: LoanType = LoanType.DEFAULT

    # Loan
    rbf_flat_fee = constants.RBF_FLAT_FEE
    loan_duration = constants.LOAN_DURATION
    loan_amount_per_monthly_income = constants.LOAN_AMOUNT_PER_MONTHLY_INCOME
    delayed_loan_repayment_increase = constants.DELAYED_LOAN_REPAYMENT_INCREASE

    # Lender
    cost_of_capital = constants.COST_OF_CAPITAL
    merchant_cost_of_acquisition = constants.MERCHANT_COST_OF_ACQUISITION
    just_in_time_funding = False
    revenue_collateralization = False
    risk_context = RiskContext()

    # Underwriting
    organic_ratio_benchmark = constants.ORGANIC_SALES_RATIO_BENCHMARK_MIN
    out_of_stock_benchmark = constants.OUT_OF_STOCK_BENCHMARK
    profit_margin_benchmark = constants.PROFIT_MARGIN_BENCHMARK_MIN
    inventory_turnover_ratio_benchmark = constants.INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG
    roas_benchmark = constants.ROAS_BENCHMARK_MIN
    debt_to_inventory_benchmark = constants.DEBT_TO_INVENTORY_BENCHMARK
    benchmark_factor = constants.BENCHMARK_FACTOR
    min_risk_score = constants.MIN_RISK_SCORE