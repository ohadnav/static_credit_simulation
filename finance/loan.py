import math
from dataclasses import dataclass
from typing import Optional

from autologging import logged, traced

from common import constants
from common.context import SimulationContext, DataGenerator
from common.primitives import Primitive
from common.util import min_max, Percent, Dollar, calculate_cagr, Date, Duration, weighted_average
from finance.underwriting import Underwriting
from seller.merchant import Merchant


@dataclass
class LoanSimulationResults:
    valuation: Optional[Dollar]
    revenues_cagr: Percent
    inventory_cagr: Percent
    net_cashflow_cagr: Percent
    valuation_cagr: Percent
    lender_profit: Dollar
    debt_to_valuation: Percent
    apr: Percent


@traced
@logged
class Loan(Primitive):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(Loan, self).__init__(data_generator)
        self.context = context
        self.merchant = merchant
        self.simulation_results: Optional[LoanSimulationResults] = None
        self.marketplace_balance = 0.0
        self.today = constants.START_DATE
        self.initial_cash = data_generator.initial_cash_ratio * merchant.annual_top_line(
            self.today) * data_generator.normal_ratio(
            data_generator.initial_cash_std)
        self.current_cash = self.initial_cash
        self.is_bankrupt = False
        self.underwriting = Underwriting(self.context, self.merchant)
        self.outstanding_debt = 0.0
        self.interest = self.context.rbf_flat_fee
        self.total_debt = 0.0
        self.current_repayment_rate = self.default_repayment_rate()
        self.current_loan_amount: Optional[Dollar] = None
        self.current_loan_start_date: Optional[Date] = None
        self.amount_history = []
        self.apr_history = []

    def default_repayment_rate(self) -> Percent:
        revenue_in_duration = self.expected_revenue_during_loan()
        if revenue_in_duration == 0:
            return constants.MAX_REPAYMENT_RATE
        rate = self.max_debt() / revenue_in_duration
        return min_max(rate, constants.MIN_REPAYMENT_RATE, constants.MAX_REPAYMENT_RATE)

    def expected_revenue_during_loan(self):
        duration_in_years = self.context.loan_duration / constants.YEAR
        return self.merchant.annual_top_line(self.today) * duration_in_years

    def add_debt(self, amount: Dollar):
        if amount > 0:
            if self.outstanding_debt == 0:
                self.current_loan_start_date = self.today
            self.current_loan_amount = amount if self.current_loan_amount is None else self.current_loan_amount + amount
        self.current_cash += amount
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

    def loan_amount(self):
        return self.context.loan_amount_per_monthly_income * self.merchant.annual_top_line(
            self.today) / constants.NUM_MONTHS

    def credit_needed(self) -> Dollar:
        return max(0.0, self.merchant.max_inventory_cost(self.today) - self.current_cash)

    def update_credit(self):
        if self.outstanding_debt == 0 and self.credit_needed() > 0:
            self.add_debt(self.approved_amount())
            self.current_repayment_rate = self.default_repayment_rate()

    def simulate_next_day(self):
        self.update_credit()
        self.simulate_sales()
        self.marketplace_payout()
        self.simulate_inventory_purchase()
        if self.current_cash < 0:
            self.bankruptcy()

    def simulate_inventory_purchase(self):
        self.current_cash -= self.merchant.inventory_cost(self.today, self.current_cash)

    def simulate_sales(self):
        self.marketplace_balance += self.merchant.gp_per_day(self.today)

    def marketplace_payout(self):
        if self.today % constants.MARKETPLACE_PAYMENT_CYCLE == 0:
            self.loan_repayment()
            self.current_cash += self.marketplace_balance
            self.marketplace_balance = 0

    def simulate(self):
        for _ in range(self.data_generator.simulated_duration):
            self.today += 1
            self.simulate_next_day()
            if self.is_bankrupt:
                break
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
        return math.pow(1 + self.interest, constants.YEAR / self.current_loan_duration()) - 1

    def bankruptcy(self):
        self.is_bankrupt = True

    def calculate_results(self):
        self.simulation_results = LoanSimulationResults(
            self.merchant.valuation(self.today, self.net_cashflow()), self.revenue_cagr(), self.inventory_cagr(),
            self.net_cashflow_cagr(), self.valuation_cagr(),
            self.lender_profit(), self.debt_to_valuation(), self.average_apr())

    def current_duration(self) -> Duration:
        return self.today - constants.START_DATE + 1

    def net_cashflow(self) -> Dollar:
        return self.current_cash - self.outstanding_debt

    def revenue_cagr(self) -> Percent:
        return calculate_cagr(
            self.merchant.annual_top_line(constants.START_DATE), self.merchant.annual_top_line(self.today),
            self.current_duration())

    def inventory_cagr(self) -> Percent:
        return calculate_cagr(
            self.merchant.inventory_value(constants.START_DATE), self.merchant.inventory_value(self.today),
            self.current_duration())

    def net_cashflow_cagr(self) -> Percent:
        return calculate_cagr(self.initial_cash, self.net_cashflow(), self.current_duration())

    def valuation_cagr(self) -> Percent:
        return calculate_cagr(
            self.merchant.valuation(constants.START_DATE, self.initial_cash),
            self.merchant.valuation(self.today, self.net_cashflow()), self.current_duration())

    def is_default(self) -> bool:
        return self.is_bankrupt or (
                self.outstanding_debt > 0 and self.current_loan_duration() > self.context.loan_duration)

    def loss(self) -> Dollar:
        loss = self.debt_to_loan_amount(self.total_debt) - self.repaid_debt(self.projected_remaining_debt())
        return loss

    def current_loan_duration(self) -> Duration:
        assert self.current_loan_start_date is not None
        return max(self.context.loan_duration, self.today - self.current_loan_start_date + 1)

    def lender_profit(self) -> Dollar:
        if self.total_debt == 0:
            return 0
        earned_interest = self.repaid_debt() * self.interest
        total_costs = self.loss() + self.cost_of_capital() + self.context.merchant_cost_of_acquisition
        return earned_interest - total_costs

    def projected_lender_profit(self) -> Dollar:
        if not self.underwriting.approved(self.today):
            return 0
        projected_costs = self.context.merchant_cost_of_acquisition + self.loan_amount() * self.context.cost_of_capital
        projected_revenues = self.loan_amount() * self.interest * self.context.expected_loans_per_year
        return projected_revenues - projected_costs

    def projected_remaining_debt(self) -> Dollar:
        if self.outstanding_debt == 0:
            return 0
        if self.is_default():
            remaining_debt = self.outstanding_debt
        else:
            revenue_in_duration = self.merchant.revenue_per_day(self.today) * self.remaining_duration()
            repayment_in_duration = revenue_in_duration * self.current_repayment_rate
            remaining_debt = max(0.0, self.outstanding_debt - repayment_in_duration)
        return remaining_debt

    def remaining_duration(self) -> Duration:
        return self.current_loan_start_date + self.current_loan_duration() - self.today

    def repaid_debt(self, outstanding_debt: Optional[Dollar] = None) -> Dollar:
        outstanding_debt = outstanding_debt if outstanding_debt else self.outstanding_debt
        repaid = self.total_debt - outstanding_debt
        return repaid

    def cost_of_capital(self) -> Dollar:
        return self.debt_to_loan_amount(self.total_debt) * self.context.cost_of_capital

    def debt_to_valuation(self) -> Percent:
        return self.total_debt / self.merchant.valuation(self.today, self.net_cashflow())

    def average_apr(self) -> Percent:
        if self.outstanding_debt > 0:
            self.close_loan()
        aprs = self.apr_history
        loan_amounts = self.amount_history
        return weighted_average(aprs, loan_amounts)


class FlatFeeRBF(Loan):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(FlatFeeRBF, self).__init__(context, data_generator, merchant)

    def calculate_repayment_rate(self) -> Percent:
        if self.today > self.context.loan_duration:
            return self.default_repayment_rate() + self.context.delayed_loan_repayment_increase
        return self.default_repayment_rate()
