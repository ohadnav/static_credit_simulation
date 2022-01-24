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
NO_RISK = 1.0
MAX_RANDOM_DEVIATION = 3.0
NUM_SIMULATED_MERCHANTS = 100
FLOAT_EQUALITY_TOLERANCE = 0.1 ** 7
CONTROLLED_STD = 0.15
VOLATILE_STD = 0.4
EXTREME_STD = 1.0
SIMULATION_DURATION = 3 * YEAR
NUM_PRODUCTS = 5
NUM_PRODUCTS_STD = EXTREME_STD
MAX_NUM_PRODUCTS = 25
FLOAT_CLOSE_TOLERANCE = 0.05
SHOW_LIVE_RATE = False

# Inventory
SHIPPING_DURATION_AVG = MONTH
SHIPPING_DURATION_MAX = 4 * MONTH
SHIPPING_DURATION_STD = VOLATILE_STD
MIN_SHIPPING_DURATION = 7
MAX_LEAD_TIME_DURATION = MONTH * 6
MANUFACTURING_DURATION_AVG = 3 * WEEK
MANUFACTURING_DURATION_MIN = 7
MANUFACTURING_DURATION_MAX = 90
MANUFACTURING_DURATION_STD = CONTROLLED_STD
COGS_MARGIN_MEDIAN = 0.4
COGS_MARGIN_MAX = 0.7
COGS_MARGIN_MIN = 0.2
COGS_MARGIN_STD = CONTROLLED_STD
INVENTORY_TURNOVER_RATIO_BENCHMARK_MIN = 1.0
INVENTORY_TURNOVER_RATIO_MEDIAN = 4.0
INVENTORY_TURNOVER_RATIO_BENCHMARK_MAX = 10.0
INVENTORY_TURNOVER_RATIO_STD = VOLATILE_STD
OUT_OF_STOCK_RATE_MEDIAN = 0.08
OUT_OF_STOCK_RATE_BENCHMARK_MIN = 0.03
OUT_OF_STOCK_RATE_STD = CONTROLLED_STD
OUT_OF_STOCK_RATE_MAX = 0.4
INVENTORY_UPFRONT_PAYMENT = 0.3
MAX_VOLUME_DISCOUNT = 0.9
VOLUME_DISCOUNT = 0.1
INVENTORY_COST_STD = CONTROLLED_STD
MIN_PURCHASE_ORDER_VALUE = 2500.0
MAX_PURCHASE_ORDER_VALUE = 10.0 ** 7
MIN_PURCHASE_ORDER_SIZE = 100
MAX_PURCHASE_ORDER_SIZE = 10 ** 6
INITIAL_STOCK_STD = EXTREME_STD
# tomorrow.value = INVENTORY_NPV_DISCOUNT_FACTOR * today.value
INVENTORY_NPV_DISCOUNT_FACTOR = 0.99
FIRST_BATCH_STD_FACTOR = 3.0

# Sales
INITIAL_CASH_RATIO = 0.01
INITIAL_CASH_STD = VOLATILE_STD
MEDIAN_PRICE = 20.0
PRICE_STD = EXTREME_STD
ORGANIC_SALES_RATE_MEDIAN = 0.45
ORGANIC_SALES_RATE_BENCHMARK = 0.9
ORGANIC_RATE_STD = CONTROLLED_STD
ORGANIC_RATE_MAX = 0.9
ORGANIC_RATE_MIN = 0.2
ROAS_BENCHMARK_MIN = 1.5
ROAS_MEDIAN = 2.0
ROAS_BENCHMARK_MAX = 4.0
MIN_ROAS = 1.2
MAX_ROAS = 5.0
ROAS_STD = CONTROLLED_STD
MARKETPLACE_PAYMENT_CYCLE = 14
GROWTH_RATIO_MAX = 3.0

# Loan
LOAN_DURATION = 120
RBF_FLAT_FEE = 0.06
LOAN_AMOUNT_PER_MONTHLY_INCOME = 1.0
DELAYED_LOAN_REPAYMENT_INCREASE = 0.05
MAX_LOAN_AMOUNT = 10.0 ** 7
MAX_MERCHANT_TOP_LINE = 10.0 ** 8
MAX_APR = 5.0

# Lender
COST_OF_CAPITAL = 0.06
MERCHANT_COST_OF_ACQUISITION = 500.0
OPERATING_COST_PER_LOAN = 2.0
DEFAULT_RISK_PREDICTOR_WEIGHT = 1.0
MAX_REPAYMENT_RATE = 0.5
MIN_REPAYMENT_RATE = 0.05
REPAYMENT_FACTOR = 0.5
EXPECTED_LOANS_PER_YEAR = 2.0
MAX_RESULTS_WEIGHT = 10 ** 7

# Costs
SGNA_RATE_MIN = 0.1
SGNA_RATE_MAX = 0.27
SGNA_RATE_STD = VOLATILE_STD
MARKETPLACE_COMMISSION = 0.20

# Underwriting
ACCOUNT_SUSPENSION_CHANCE = 0.05
ACCOUNT_SUSPENSION_DURATION = 30
DEBT_TO_INVENTORY_BENCHMARK = 0.5
PROFIT_MARGIN_BENCHMARK_MIN = 0.07
PROFIT_MARGIN_BENCHMARK_MAX = 0.2
PROFIT_MARGIN_ADJUSTMENT = 0.02
MIN_RISK_SCORE = 0.4
DEFAULT_RISK_MIN_THRESHOLD = 0.2
LOW_UNDERWRITING_SENSITIVITY = 1.0
MEDIUM_UNDERWRITING_SENSITIVITY = 2.5
HIGH_UNDERWRITING_SENSITIVITY = 4.0
AGG_SCORE_BENCHMARK = 0.8
