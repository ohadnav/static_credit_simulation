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

# Inventory
SHIPPING_TIME_MAX = 55
SHIPPING_TIME_MIN = 22
SHIPPING_TIME_DELAY = 7
SHIPPING_DELAY_MAX = SHIPPING_TIME_MAX * 2
SHIPPING_VOLATILITY = 0.95
MANUFACTURING_TIME_MIN = 30
MANUFACTURING_TIME_MAX = 60
MAX_LEAD_TIME = MANUFACTURING_TIME_MAX + SHIPPING_TIME_MAX
COGS_MARGIN_BENCHMARK_MIN = 0.3
COGS_MARGIN_BENCHMARK_MAX = 0.45
COGS_MARGIN_MAX = 0.8
INVENTORY_TURNOVER_RATIO_BENCHMARK_MIN = 2
INVENTORY_TURNOVER_RATIO_BENCHMARK_AVG = 4
INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX = 11
INVENTORY_TURNOVER_RATIO_STD = 1
OUT_OF_STOCK_BENCHMARK = 0.08
OUT_OF_STOCK_STD = 1
INVENTORY_UPFRONT_PAYMENT = 0.3
MAX_VOLUME_DISCOUNT = 0.9
INVENTORY_BUFFER = 0.1
VOLUME_DISCOUNT = 0.1
INVENTORY_COST_STD = 0.5
MIN_PURCHASE_ORDER_VALUE = 5000
MIN_PURCHASE_ORDER_SIZE = 100
COGS_MARGIN_STD = 0.25
INITIAL_STOCK_STD = 5

# Sales
INITIAL_CASH_RATIO = 0.02
INITIAL_CASH_STD = 2
MEDIAN_PRICE = 20
PRICE_STD = 5
ORGANIC_GROWTH_RATE = 0.02
ORGANIC_SALES_CYCLE = WEEK * 2
SALES_VELOCITY_DURATION = WEEK * 2
ORGANIC_SALES_RATIO_BENCHMARK_MIN = 0.25
ORGANIC_SALES_RATIO_BENCHMARK_MAX = 0.75
ORGANIC_RATIO_VARIANCE = 0.2
ROAS_BENCHMARK_MIN = 1.5
ROAS_BENCHMARK_MAX = 4
MARKETPLACE_PAYMENT_CYCLE = 14
EXPECTED_SALES_GROWTH = 0.5
SALES_GROWTH_STD = 3
SHARE_OF_GROWERS = 0.66
NET_PROFIT_MARGIN = 0.1
# TODO: account for seasonality
AVERAGE_SALES_VOLATILITY = 0.2
ROAS_VOLATILITY = 0.2
ROAS_VARIANCE = 1
MARKETING_CREDIT_BUFFER = 0.2
ROAS_STD = 0.3
ORGANIC_SALES_VOLATILITY = 0.5
ORGANIC_SALES_VOLATILITY_STD = 0.5
SALES_VOLATILITY_CYCLE = 21
CASHFLOW_BUFFER_FROM_TOP_LINE = 0.05

# Loan
LOAN_DURATION = 90
RBF_FLAT_FEE = 0.06
LOAN_AMOUNT_PER_MONTHLY_INCOME = 1.0
LIMIT_FACTOR = 10
APR_MIN = 0.1
APR_FACTOR = 10
DELAYED_LOAN_REPAYMENT_INCREASE = 0.05

# Lender
COST_OF_CAPITAL = 0.1
MERCHANT_COST_OF_ACQUISITION = 1000
DEFAULT_RISK_PREDICTOR_WEIGHT = 1
DEFAULT_RISK_MIN_THRESHOLD = 0.25
MAX_REPAYMENT_RATE = 0.5
MIN_REPAYMENT_RATE = 0.05
REPAYMENT_FACTOR = 0.5

# Costs
SGNA_RATIO_MIN = 0.1
SGNA_RATIO_MAX = 0.27
SGNA_PAYMENT_CYCLE = 30
SGNA_STD = 1
MARKETPLACE_COMMISSION = 0.20

# Underwriting
ACCOUNT_SUSPENSION_CHANCE = 0.01
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
NUM_SIMULATED_MERCHANTS = 1000000


class LoanType(Enum):
    DEFAULT = 'Loan'
    FLAT_FEE = 'FlatFeeRBF'
    LINE_OF_CREDIT = 'LineOfCredit'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCredit'