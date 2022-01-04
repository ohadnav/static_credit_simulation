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
        self.total_debt = 0.0
        self.current_repayment_rate: Optional[Percent] = None
        self.current_loan_amount: Optional[Dollar] = None
        self.last_added_debt_date: Optional[Date] = None
        self.amount_history = []
        self.apr_history = []

    def default_repayment_rate(self) -> Percent:
        revenue_in_duration = self.expected_revenue_during_loan()
        rate = self.max_debt() / revenue_in_duration
        return min_max(rate, constants.MIN_REPAYMENT_RATE, constants.MAX_REPAYMENT_RATE)

    def expected_revenue_during_loan(self):
        duration_in_years = self.context.loan_duration / constants.YEAR
        return self.merchant.annual_top_line(self.today) * duration_in_years

    def calculate_repayment_rate(self) -> Percent:
        return self.current_repayment_rate

    def add_debt(self, amount: Dollar):
        if amount > 0 and self.outstanding_debt == 0:
            self.last_added_debt_date = self.today
        self.current_cash += amount
        new_debt = amount * (1 + self.fixed_interest())
        self.outstanding_debt += new_debt
        self.total_debt += new_debt

    def fixed_interest(self) -> Percent:
        return self.context.rbf_flat_fee

    def debt_to_loan_amount(self, debt: Dollar) -> Dollar:
        return debt / (1 + self.fixed_interest())

    def max_debt(self) -> Dollar:
        return self.loan_amount() * (1 + self.fixed_interest())

    def approved_amount(self) -> Dollar:
        if not self.underwriting.approved():
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
        for _ in range(constants.SIMULATION_DURATION):
            self.today += 1
            self.simulate_next_day()
            if self.is_bankrupt:
                break
        self.calculate_results()

    def loan_repayment(self):
        if self.outstanding_debt > 0:
            repayment = min(self.outstanding_debt, self.marketplace_balance * self.calculate_repayment_rate())
            self.current_cash -= repayment
            self.outstanding_debt -= repayment
            if self.outstanding_debt == 0:
                self.close_loan()

    def close_loan(self):
        last_apr = math.pow(1 + self.fixed_interest(), self.current_loan_duration() / constants.YEAR)
        last_amount = self.current_loan_duration()
        self.amount_history.append(last_amount)
        self.apr_history.append(last_apr)
        self.current_loan_amount = None
        self.last_added_debt_date = None

    def bankruptcy(self):
        self.is_bankrupt = True

    def calculate_results(self):
        return LoanSimulationResults(
            self.revenue_cagr(), self.inventory_cagr(), self.net_cashflow_cagr(), self.valuation_cagr(),
            self.lender_profit(), self.debt_to_valuation(), self.apr())

    def current_duration(self):
        return self.today - constants.START_DATE + 1

    def net_cashflow(self) -> Dollar:
        return self.current_cash - self.outstanding_debt

    def revenue_cagr(self) -> Percent:
        return calculate_cagr(self.merchant.annual_top_line(constants.START_DATE), self.merchant.annual_top_line(self.today), self.current_duration())

    def inventory_cagr(self) -> Percent:
        return calculate_cagr(self.merchant.inventory_value(constants.START_DATE), self.merchant.inventory_value(self.today), self.current_duration())

    def net_cashflow_cagr(self) -> Percent:
        return calculate_cagr(            self.initial_cash, self.net_cashflow(),            self.current_duration())

    def valuation_cagr(self) -> Percent:
        return calculate_cagr(self.merchant.valuation(constants.START_DATE, self.initial_cash), self.merchant.valuation(self.today, self.net_cashflow()), self.current_duration())

    def unpaid_debt(self) -> Dollar:
        if self.is_bankrupt:
            return self.outstanding_debt
        if self.outstanding_debt == 0:
            return 0
        remaining_duration = self.context.loan_duration - self.current_loan_duration()
        revenue_in_duration = self.merchant.revenue_per_day(self.today) * remaining_duration
        repayment_in_duration = revenue_in_duration * self.current_repayment_rate
        remaining_debt = max(0.0,self.outstanding_debt - repayment_in_duration)
        return remaining_debt

    def current_loan_duration(self) -> Duration:
        return max(self.context.loan_duration, self.today - self.last_added_debt_date + 1)

    def lender_profit(self) -> Dollar:
        if self.total_debt == 0:
            return 0
        repaid_debt = self.total_debt - self.outstanding_debt
        earned_interest = repaid_debt * self.fixed_interest()
        total_costs = self.unpaid_debt() + self.additional_lender_costs()
        return earned_interest - total_costs

    def additional_lender_costs(self) -> Dollar:
        cost_of_capital = self.debt_to_loan_amount(self.total_debt) * self.context.cost_of_capital
        return cost_of_capital + self.context.merchant_cost_of_acquisition

    def debt_to_valuation(self) -> Percent:
        return self.total_debt / self.merchant.valuation(self.today, self.net_cashflow())

    def apr(self) -> Percent:
        current_apr, current_amount = self.estimate_current_apr()
        aprs = self.apr_history
        loan_amounts = self.amount_history
        aprs.append(current_apr)
        loan_amounts.append(current_amount)
        return weighted_average(aprs, loan_amounts)



class FlatFeeRBF(Loan):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(FlatFeeRBF, self).__init__(context, data_generator, merchant)

    def calculate_repayment_rate(self) -> Percent:
        if self.today > self.context.loan_duration:
            return self.default_repayment_rate() + self.context.delayed_loan_repayment_increase
        return self.default_repayment_rate()
