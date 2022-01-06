# Runtime
from enum import Enum

OUT_DIR = 'out/'

# Time frame
WEEK = 7
MONTH = 30
YEAR = 365
NUM_MONTHS = YEAR // MONTH
SIMULATION_DURATION = YEAR
START_DATE = 1

FLOAT_ADJUSTMENT = 0.001

# Inventory
SHIPPING_DURATION_AVG = MONTH
SHIPPING_DURATION_MAX = 4 * MONTH
SHIPPING_DURATION_STD = 0.5
MIN_SHIPPING_DURATION = 7
MAX_LEAD_TIME_DURATION = MONTH * 6
MANUFACTURING_DURATION_AVG = 3 * WEEK
MANUFACTURING_DURATION_MIN = 7
MANUFACTURING_DURATION_MAX = 90
MANUFACTURING_DURATION_STD = 0.5
COGS_MARGIN_BENCHMARK_AVG = 0.35
COGS_MARGIN_MAX = 0.7
COGS_MARGIN_MIN = 0.2
INVENTORY_TURNOVER_RATIO_BENCHMARK_MIN = 2
INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG = 4
INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX = 11
INVENTORY_TURNOVER_RATIO_STD = 0.5
OUT_OF_STOCK_RATE_BENCHMARK = 0.08
OUT_OF_STOCK_RATE_STD = 1
INVENTORY_UPFRONT_PAYMENT = 0.3
MAX_VOLUME_DISCOUNT = 0.9
VOLUME_DISCOUNT = 0.1
INVENTORY_COST_STD = 0.1
MIN_PURCHASE_ORDER_VALUE = 10000
MIN_PURCHASE_ORDER_SIZE = 100
COGS_MARGIN_STD = 0.1
INITIAL_STOCK_STD = 2
# tomorrow.value = INVENTORY_NPV_DISCOUNT_FACTOR * today.value
INVENTORY_NPV_DISCOUNT_FACTOR = 0.99

# Sales
INITIAL_CASH_RATIO = 0.02
INITIAL_CASH_STD = 2
MEDIAN_PRICE = 20
PRICE_STD = 1.5
ORGANIC_SALES_RATIO_BENCHMARK_MIN = 0.25
ORGANIC_SALES_RATIO_MEDIAN = 0.5
ORGANIC_SALES_RATIO_BENCHMARK_MAX = 0.75
ORGANIC_RATE_STD = 0.5
ROAS_BENCHMARK_MIN = 1.5
ROAS_MEDIAN = 2
ROAS_BENCHMARK_MAX = 4
MARKETPLACE_PAYMENT_CYCLE = 14
GROWTH_RATE_AVG = 0.5
GROWTH_RATE_STD = 3
SHARE_OF_GROWERS = 0.66
NET_PROFIT_MARGIN = 0.1
MIN_ROAS = 1.2
MAX_ROAS = 5
ROAS_STD = 0.25
ORGANIC_SALES_VOLATILITY = 0.5
CASHFLOW_BUFFER_FROM_TOP_LINE = 0.05

# Loan
LOAN_DURATION = 90
RBF_FLAT_FEE = 0.06
LOAN_AMOUNT_PER_MONTHLY_INCOME = 1.0
DELAYED_LOAN_REPAYMENT_INCREASE = 0.05

# Lender
COST_OF_CAPITAL = 0.1
MERCHANT_COST_OF_ACQUISITION = 1000
DEFAULT_RISK_PREDICTOR_WEIGHT = 1
DEFAULT_RISK_MIN_THRESHOLD = 0.25
MAX_REPAYMENT_RATE = 0.5
MIN_REPAYMENT_RATE = 0.05
REPAYMENT_FACTOR = 0.5
EXPECTED_LOANS_PER_YEAR = 2

# Costs
SGNA_RATIO_MIN = 0.1
SGNA_RATIO_MAX = 0.27
SGNA_STD = 0.2
MARKETPLACE_COMMISSION = 0.20

# Underwriting
ACCOUNT_SUSPENSION_CHANCE = 0.05
ACCOUNT_SUSPENSION_DURATION = 30
DEBT_TO_INVENTORY_BENCHMARK = 0.5
PROFIT_MARGIN_BENCHMARK_MIN = 0.07
PROFIT_MARGIN_BENCHMARK_MAX = 0.15
BENCHMARK_FACTOR = 1.2
MIN_RISK_SCORE = 0.25

# Analysis
SENSITIVITY = 0.05
NO_VOLATILITY = 1.0
NO_RISK = 1
MAX_RANDOM_DEVIATION = 3
NUM_SIMULATED_MERCHANTS = 10000
NUM_PRODUCTS = 20
MAX_NUM_PRODUCTS = 100


class LoanType(Enum):
    DEFAULT = 'Loan'
    FLAT_FEE = 'FlatFeeRBF'
    LINE_OF_CREDIT = 'LineOfCredit'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCredit'
    NO_CAPITAL = 'NoCapitalLoan'
