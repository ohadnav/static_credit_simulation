import math
from dataclasses import dataclass
from typing import Optional, MutableMapping

from common import constants
from common.context import SimulationContext, DataGenerator
from common.primitives import Primitive
from common.util import min_max, Percent, Dollar, calculate_cagr, Date, Duration, weighted_average, inverse_cagr
from finance.underwriting import Underwriting
from seller.merchant import Merchant


@dataclass
class LoanSimulationResults:
    valuation: Dollar
    revenues_cagr: Percent
    inventory_cagr: Percent
    net_cashflow_cagr: Percent
    valuation_cagr: Percent
    lender_profit: Dollar
    debt_to_valuation: Percent
    apr: Percent
    bankruptcy_rate: Percent

    def __str__(self):
        s = []
        for k, v in vars(self).items():
            s.append(f'{k}={round(v, 2)}')
        return ' '.join(s)


class Loan(Primitive):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(Loan, self).__init__(data_generator)
        self.context = context
        self.merchant = merchant
        self.simulation_results: Optional[LoanSimulationResults] = None
        self.marketplace_balance = 0.0
        self.today = constants.START_DATE
        self.initial_cash = data_generator.initial_cash_ratio * merchant.annual_top_line(self.today)
        self.current_cash = self.initial_cash
        self.bankruptcy_date: Optional[Date] = None
        self.underwriting = Underwriting(self.context, self.merchant)
        self.outstanding_debt = 0.0
        self.interest = self.context.rbf_flat_fee
        self.total_debt = 0.0
        self.total_revenues = 0.0
        self.total_duration_in_debt = 0
        self.current_repayment_rate = self.default_repayment_rate()
        self.current_loan_amount: Optional[Dollar] = None
        self.current_loan_start_date: Optional[Date] = None
        self.amount_history = []
        self.apr_history = []
        self.cash_history: MutableMapping[Date, Dollar] = {self.today: self.initial_cash}

    def default_repayment_rate(self) -> Percent:
        revenue_in_duration = self.expected_revenue_during_loan()
        if revenue_in_duration == 0:
            return constants.MAX_REPAYMENT_RATE
        rate = self.max_debt() / revenue_in_duration
        rate = min_max(rate, constants.MIN_REPAYMENT_RATE, constants.MAX_REPAYMENT_RATE)
        return rate

    def expected_revenue_during_loan(self) -> Dollar:
        duration_in_years = self.context.loan_duration / constants.YEAR
        revenue = self.merchant.annual_top_line(self.today) * duration_in_years
        return revenue

    def add_debt(self, amount: Dollar):
        assert amount > 0
        if self.outstanding_debt == 0:
            self.current_loan_start_date = self.today
            self.total_duration_in_debt += 1
        self.current_loan_amount = amount if self.current_loan_amount is None else self.current_loan_amount + amount
        self.current_cash += amount
        self.cash_history[self.today] = self.current_cash
        new_debt = amount * (1 + self.interest)
        self.outstanding_debt += new_debt
        self.total_debt += new_debt

    def debt_to_loan_amount(self, debt: Dollar) -> Dollar:
        return debt / (1 + self.interest)

    def max_debt(self) -> Dollar:
        return self.loan_amount() * (1 + self.interest)

    def approved_amount(self) -> Dollar:
        if not self.underwriting.approved(self.today) or self.projected_lender_profit() <= 0:
            return 0.0
        return self.loan_amount()

    def loan_amount(self) -> Dollar:
        return self.context.loan_amount_per_monthly_income * self.merchant.annual_top_line(
            self.today) / constants.NUM_MONTHS

    def credit_needed(self) -> Dollar:
        buffer = self.merchant.committed_purchase_orders(self.today)
        max_cost_for_growth = self.merchant.max_cash_needed(self.today)
        cash_gap = buffer + max_cost_for_growth - self.current_cash
        return max(0.0, cash_gap)

    def update_credit(self):
        if self.outstanding_debt > 0:
            self.total_duration_in_debt += 1
        if self.outstanding_debt == 0 and self.credit_needed() > 0:
            amount = self.approved_amount()
            if self.credit_needed() < amount / 2:
                amount /= 2
            if amount > 0:
                self.add_debt(amount)
                self.current_repayment_rate = self.default_repayment_rate()

    def simulate_day(self):
        self.update_credit()
        self.simulate_sales()
        self.marketplace_payout()
        self.simulate_inventory_purchase()
        if self.current_cash + constants.FLOAT_ADJUSTMENT < 0:
            self.on_bankruptcy()

    def simulate_inventory_purchase(self):
        inventory_cost = self.merchant.inventory_cost(self.today, self.current_cash)
        self.current_cash -= inventory_cost
        if inventory_cost > 0:
            self.cash_history[self.today] = self.current_cash

    def simulate_sales(self):
        self.total_revenues += self.merchant.revenue_per_day(self.today)
        self.marketplace_balance += self.merchant.gp_per_day(self.today)

    def marketplace_payout(self):
        if self.today % constants.MARKETPLACE_PAYMENT_CYCLE == 0:
            if self.marketplace_balance == 0:
                if not self.merchant.has_future_revenue(self.today):
                    self.on_bankruptcy()
            self.loan_repayment()
            self.current_cash += self.marketplace_balance
            self.cash_history[self.today] = self.current_cash
            self.marketplace_balance = 0

    def simulate(self):
        assert self.today == constants.START_DATE
        for i in range(self.data_generator.simulated_duration):
            self.simulate_day()
            if self.bankruptcy_date:
                break
            self.today += 1
        self.today = min(self.data_generator.simulated_duration, self.today)
        self.calculate_results()

    def loan_repayment(self):
        if self.outstanding_debt > 0:
            repayment = min(self.outstanding_debt, self.marketplace_balance * self.current_repayment_rate)
            self.current_cash -= repayment
            self.outstanding_debt -= repayment
            if self.outstanding_debt == 0:
                self.close_loan()

    def close_loan(self):
        if self.current_loan_amount is None:
            return
        self.amount_history.append(self.current_loan_amount)
        self.apr_history.append(self.current_loan_apr())
        self.current_loan_amount = None
        self.current_loan_start_date = None

    def current_loan_apr(self) -> Percent:
        # TODO: calculate per actual interest payments
        apr = math.pow(1 + self.interest, constants.YEAR / self.current_loan_duration()) - 1
        return apr

    def on_bankruptcy(self):
        self.bankruptcy_date = self.today

    def calculate_results(self):
        self.simulation_results = LoanSimulationResults(
            self.merchant.valuation(self.today, self.net_cashflow()), self.revenue_cagr(), self.inventory_cagr(),
            self.net_cashflow_cagr(), self.valuation_cagr(),
            self.lender_profit(), self.debt_to_valuation(), self.average_apr(), self.calculate_bankruptcy_rate())

    def calculate_bankruptcy_rate(self) -> Percent:
        if self.bankruptcy_date is None:
            return 0
        remaining_duration = self.data_generator.simulated_duration - self.bankruptcy_date + 1
        rate = remaining_duration / self.data_generator.simulated_duration
        return rate

    def duration_until_today(self) -> Duration:
        return self.today - constants.START_DATE + 1

    def net_cashflow(self) -> Dollar:
        ncf = self.current_cash - self.outstanding_debt
        return ncf

    def revenue_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.annual_top_line(constants.START_DATE), self.total_revenues,
            self.duration_until_today())
        return cagr

    def inventory_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.inventory_value(constants.START_DATE), self.merchant.inventory_value(self.today),
            self.duration_until_today())
        return cagr

    def net_cashflow_cagr(self) -> Percent:
        cagr = calculate_cagr(self.initial_cash, self.net_cashflow(), self.duration_until_today())
        return cagr

    def valuation_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.valuation(constants.START_DATE, self.initial_cash),
            self.merchant.valuation(self.today, self.net_cashflow()), self.duration_until_today())
        return cagr

    def is_default(self) -> bool:
        defaulted = self.bankruptcy_date is not None or (
                self.context.duration_based_default and self.outstanding_debt > 0 and self.current_loan_duration() >
                self.context.loan_duration)
        return defaulted

    def loss(self) -> Dollar:
        loss = self.debt_to_loan_amount(self.total_debt) - self.repaid_debt(self.projected_remaining_debt())
        return loss

    def current_loan_duration(self) -> Duration:
        assert self.current_loan_start_date is not None
        duration = max(self.context.loan_duration, self.today - self.current_loan_start_date + 1)
        return duration

    def lender_profit(self) -> Dollar:
        if self.total_debt == 0:
            return 0
        earned_interest = self.repaid_debt() * self.average_apr()
        total_costs = self.loss() + self.cost_of_capital() + self.context.merchant_cost_of_acquisition
        profit = earned_interest - total_costs
        return profit

    def projected_lender_profit(self) -> Dollar:
        cost_of_capital = self.loan_amount() * inverse_cagr(self.context.cost_of_capital, self.context.loan_duration)
        cost_of_acquisition = self.context.merchant_cost_of_acquisition if self.total_debt == 0 else 0
        projected_costs = cost_of_capital + cost_of_acquisition
        expected_annual_credit = self.loan_amount() * self.context.expected_loans_per_year
        projected_revenues = self.context.expected_apr * expected_annual_credit
        projected_profit = projected_revenues - projected_costs
        return projected_profit

    def projected_remaining_debt(self) -> Dollar:
        if self.outstanding_debt == 0:
            return 0
        if self.is_default():
            remaining_debt = self.outstanding_debt
        else:
            revenue_in_duration = self.merchant.annual_top_line(self.today) * self.remaining_duration() / constants.YEAR
            repayment_in_duration = revenue_in_duration * self.current_repayment_rate
            remaining_debt = max(0.0, self.outstanding_debt - repayment_in_duration)
        return remaining_debt

    def remaining_duration(self) -> Duration:
        if self.context.duration_based_default:
            return self.current_loan_start_date + self.current_loan_duration() - self.today
        else:
            return self.context.loan_duration

    def repaid_debt(self, outstanding_debt: Optional[Dollar] = None) -> Dollar:
        outstanding_debt = outstanding_debt if outstanding_debt is not None else self.outstanding_debt
        repaid = self.total_debt - outstanding_debt
        return repaid

    def cost_of_capital(self) -> Dollar:
        # TODO: calculate per actual interest payments
        coc = self.debt_to_loan_amount(self.total_debt) * inverse_cagr(
            self.context.cost_of_capital, self.total_duration_in_debt)
        return coc

    def debt_to_valuation(self) -> Percent:
        dtv = self.total_debt / self.merchant.valuation(self.today, self.net_cashflow())
        return dtv

    def average_apr(self) -> Percent:
        if self.outstanding_debt > 0:
            self.close_loan()
        aprs = self.apr_history
        loan_amounts = self.amount_history
        apr = weighted_average(aprs, loan_amounts)
        return apr


class FlatFeeRBF(Loan):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(FlatFeeRBF, self).__init__(context, data_generator, merchant)

    def calculate_repayment_rate(self) -> Percent:
        if self.today > self.context.loan_duration:
            return self.default_repayment_rate() + self.context.delayed_loan_repayment_increase
        return self.default_repayment_rate()


class NoCapitalLoan(Loan):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(NoCapitalLoan, self).__init__(context, data_generator, merchant)

    def add_debt(self, amount: Dollar):
        pass

    def loan_amount(self) -> Dollar:
        return 0
