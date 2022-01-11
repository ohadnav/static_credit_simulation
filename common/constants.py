# Runtime
from enum import Enum

OUT_DIR = 'out/'

# Time frame
WEEK = 7
MONTH = 30
YEAR = 365
NUM_MONTHS = YEAR // MONTH
START_DATE = 1

# Analysis
SENSITIVITY = 0.05
NO_VOLATILITY = 1.0
NO_RISK = 1
MAX_RANDOM_DEVIATION = 3
NUM_SIMULATED_MERCHANTS = 1000
NUM_PRODUCTS = 3
MAX_NUM_PRODUCTS = 10
FLOAT_ADJUSTMENT = 0.001
CONTROLLED_STD = 0.1
VOLATILE_STD = 0.25
SIMULATION_DURATION = 3 * YEAR

# Inventory
SHIPPING_DURATION_AVG = MONTH
SHIPPING_DURATION_MAX = 4 * MONTH
SHIPPING_DURATION_STD = VOLATILE_STD
MIN_SHIPPING_DURATION = 7
MAX_LEAD_TIME_DURATION = MONTH * 6
MANUFACTURING_DURATION_AVG = 3 * WEEK
MANUFACTURING_DURATION_MIN = 7
MANUFACTURING_DURATION_MAX = 90
MANUFACTURING_DURATION_STD = VOLATILE_STD
COGS_MARGIN_BENCHMARK_AVG = 0.4
COGS_MARGIN_MAX = 0.7
COGS_MARGIN_MIN = 0.2
INVENTORY_TURNOVER_RATIO_BENCHMARK_MIN = 2
INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG = 4
INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX = 11
INVENTORY_TURNOVER_RATIO_STD = VOLATILE_STD
OUT_OF_STOCK_RATE_MEDIAN = 0.08
OUT_OF_STOCK_RATE_STD = CONTROLLED_STD
OUT_OF_STOCK_RATE_MAX = 0.4
INVENTORY_UPFRONT_PAYMENT = 0.3
MAX_VOLUME_DISCOUNT = 0.9
VOLUME_DISCOUNT = 0.1
INVENTORY_COST_STD = CONTROLLED_STD
MIN_PURCHASE_ORDER_VALUE = 5000
MIN_PURCHASE_ORDER_SIZE = 100
COGS_MARGIN_STD = CONTROLLED_STD
INITIAL_STOCK_STD = CONTROLLED_STD
# tomorrow.value = INVENTORY_NPV_DISCOUNT_FACTOR * today.value
INVENTORY_NPV_DISCOUNT_FACTOR = 0.99

# Sales
INITIAL_CASH_RATIO = 0.01
INITIAL_CASH_STD = VOLATILE_STD
MEDIAN_PRICE = 20
PRICE_STD = 1.5
ORGANIC_SALES_RATIO_BENCHMARK_MIN = 0.25
ORGANIC_SALES_RATIO_MEDIAN = 0.4
ORGANIC_SALES_RATIO_BENCHMARK_MAX = 0.75
ORGANIC_RATE_STD = VOLATILE_STD
ORGANIC_RATE_MAX = 0.9
ORGANIC_RATE_MIN = 0.2
ROAS_BENCHMARK_MIN = 1.5
ROAS_MEDIAN = 1.7
ROAS_BENCHMARK_MAX = 4
MIN_ROAS = 1.2
MAX_ROAS = 5
ROAS_STD = CONTROLLED_STD
MARKETPLACE_PAYMENT_CYCLE = 14
GROWTH_RATIO_MAX = 3

# Loan
LOAN_DURATION = 120
RBF_FLAT_FEE = 0.06
LOAN_AMOUNT_PER_MONTHLY_INCOME = 1.0
DELAYED_LOAN_REPAYMENT_INCREASE = 0.05

# Lender
COST_OF_CAPITAL = 0.06
MERCHANT_COST_OF_ACQUISITION = 500
DEFAULT_RISK_PREDICTOR_WEIGHT = 1
MAX_REPAYMENT_RATE = 0.5
MIN_REPAYMENT_RATE = 0.05
REPAYMENT_FACTOR = 0.5
EXPECTED_LOANS_PER_YEAR = 2

# Costs
SGNA_RATIO_MIN = 0.1
SGNA_RATIO_MAX = 0.27
SGNA_STD = CONTROLLED_STD
MARKETPLACE_COMMISSION = 0.20

# Underwriting
ACCOUNT_SUSPENSION_CHANCE = 0.05
ACCOUNT_SUSPENSION_DURATION = 30
DEBT_TO_INVENTORY_BENCHMARK = 0.5
PROFIT_MARGIN_BENCHMARK_MIN = 0.07
PROFIT_MARGIN_BENCHMARK_MAX = 0.2
PROFIT_MARGIN_ADJUSTMENT = 0.05
BENCHMARK_FACTOR = 2
MIN_RISK_SCORE = 0.4
DEFAULT_RISK_MIN_THRESHOLD = 0.2


class LoanSimulationType(Enum):
    DEFAULT = 'LoanSimulation'
    INCREASING_REBATE = 'IncreasingRebateLoanSimulation'
    LINE_OF_CREDIT = 'LineOfCreditSimulation'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCreditSimulation'
    NO_CAPITAL = 'NoCapitalLoanSimulation'
