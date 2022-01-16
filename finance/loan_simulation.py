from dataclasses import dataclass
from typing import Optional, MutableMapping, List

from common import constants
from common.context import SimulationContext, DataGenerator
from common.numbers import Float, Percent, Date, Duration, Dollar, O, O_INT
from common.primitive import Primitive
from common.util import min_max, calculate_cagr, weighted_average, inverse_cagr
from finance.underwriting import Underwriting
from seller.merchant import Merchant


@dataclass(unsafe_hash=True)
class LoanSimulationResults:
    valuation: Dollar
    revenues_cagr: Percent
    inventory_cagr: Percent
    net_cashflow_cagr: Percent
    valuation_cagr: Percent
    lender_profit: Dollar
    total_credit: Dollar
    debt_to_valuation: Percent
    apr: Percent
    bankruptcy_rate: Percent

    def __str__(self):
        s = []
        for k, v in vars(self).items():
            s.append(f'{k}={round(v, 2)}')
        return ' '.join(s)


@dataclass(unsafe_hash=True)
class Loan:
    amount: Dollar
    duration: Duration
    outstanding_debt: Dollar
    start_date: Date

    def update_duration(self, today: Date):
        assert today >= self.start_date
        duration = today - self.start_date + 1
        if self.outstanding_debt == O:
            self.duration = duration
        else:
            self.duration = Duration.max(self.duration, duration)

    def remaining_duration(self, today: Date) -> Duration:
        assert today >= self.start_date
        duration = self.start_date + self.duration - today
        return Duration.max(duration, O_INT)


class LoanSimulation(Primitive):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(LoanSimulation, self).__init__(data_generator)
        self.context = context
        self.merchant = merchant
        self.simulation_results: Optional[LoanSimulationResults] = None
        self.marketplace_balance = O
        self.today = Date(self.data_generator.start_date)
        self.initial_cash = data_generator.initial_cash_ratio * merchant.annual_top_line(self.today)
        self.current_cash = self.initial_cash
        self.bankruptcy_date: Optional[Date] = None
        self.underwriting = Underwriting(self.context, self.data_generator, self.merchant)
        self.interest = self.context.rbf_flat_fee
        self.total_credit = O
        self.total_revenues = O
        self.current_repayment_rate = self.default_repayment_rate()
        self.loans_history: List[Loan] = []
        self.active_loans: List[Loan] = []
        self.cash_history: MutableMapping[Date, Dollar] = {self.today: self.initial_cash}

    def outstanding_debt(self) -> Dollar:
        return Float.sum([loan.outstanding_debt for loan in self.active_loans])

    def default_repayment_rate(self) -> Percent:
        revenue_in_duration = self.expected_revenue_during_loan()
        if revenue_in_duration == O:
            return constants.MAX_REPAYMENT_RATE
        rate = self.max_debt() / revenue_in_duration
        rate = min_max(rate, constants.MIN_REPAYMENT_RATE, constants.MAX_REPAYMENT_RATE)
        return rate

    def expected_revenue_during_loan(self) -> Dollar:
        duration_in_years = self.context.loan_duration / constants.YEAR
        revenue = self.merchant.annual_top_line(self.today) * duration_in_years
        return revenue

    def add_debt(self, amount: Dollar):
        assert amount > O
        new_debt = self.amount_to_debt(amount)
        self.active_loans.append(Loan(amount, self.context.loan_duration, new_debt, self.today))
        self.current_cash += amount
        self.cash_history[self.today] = self.current_cash
        self.total_credit += new_debt

    def amount_to_debt(self, amount: Dollar):
        return amount * (1 + self.interest)

    def debt_to_loan_amount(self, debt: Dollar) -> Dollar:
        return debt / (1 + self.interest)

    def max_debt(self) -> Dollar:
        return self.amount_to_debt(self.loan_amount())

    def approved_amount(self) -> Dollar:
        if not self.underwriting.approved(self.today) or self.projected_lender_profit() <= O:
            return O
        return self.loan_amount()

    def loan_amount(self) -> Dollar:
        amount = self.merchant.annual_top_line(
            self.today) * self.context.loan_amount_per_monthly_income / constants.NUM_MONTHS
        amount = Float.min(amount, self.context.max_loan_amount)
        return amount

    def credit_needed(self) -> Dollar:
        buffer = self.merchant.committed_purchase_orders(self.today)
        max_cost_for_growth = self.merchant.max_cash_needed(self.today)
        cash_gap = buffer + max_cost_for_growth - self.current_cash
        return Float.max(O, cash_gap)

    def update_credit(self):
        if self.should_take_loan():
            amount = self.calculate_amount()
            if amount > O:
                self.add_debt(amount)
                self.current_repayment_rate = self.default_repayment_rate()

    def should_take_loan(self) -> bool:
        if self.merchant.annual_top_line(self.today) > self.context.max_merchant_top_line:
            return False
        return self.outstanding_debt() == O and self.credit_needed() > O

    def calculate_amount(self) -> Dollar:
        amount = self.approved_amount()
        return amount

    def simulate_day(self):
        self.update_credit()
        self.simulate_sales()
        self.marketplace_payout()
        self.simulate_inventory_purchase()
        if self.current_cash < O:
            self.on_bankruptcy()

    def simulate_inventory_purchase(self):
        inventory_cost = self.merchant.inventory_cost(self.today, self.current_cash)
        self.current_cash -= inventory_cost
        if inventory_cost > O:
            self.cash_history[self.today] = self.current_cash

    def simulate_sales(self):
        self.total_revenues += self.merchant.revenue_per_day(self.today)
        self.marketplace_balance += self.merchant.gp_per_day(self.today)

    def marketplace_payout(self):
        if self.today % constants.MARKETPLACE_PAYMENT_CYCLE == 0:
            if self.marketplace_balance == O:
                if not self.merchant.has_future_revenue(self.today):
                    self.on_bankruptcy()
            self.loan_repayment()
            self.current_cash += self.marketplace_balance
            self.cash_history[self.today] = self.current_cash
            self.marketplace_balance = O

    def simulate(self):
        assert self.today == self.data_generator.start_date
        for i in range(self.data_generator.simulated_duration):
            self.simulate_day()
            if self.bankruptcy_date:
                break
            if self.merchant.annual_top_line(self.today) > self.context.max_merchant_top_line:
                break
            self.today += Duration(1)
        self.today = Duration.min(self.data_generator.simulated_duration, self.today)
        self.calculate_results()

    def repay_loans(self, total_repayment: Dollar):
        remaining_repayment = total_repayment
        while remaining_repayment > O and len(self.active_loans):
            # TODO: "close loans" per each repayment with the earliest loan start_date as duration
            loan = self.active_loans[0]
            max_repayment = Float.min(loan.outstanding_debt, remaining_repayment)
            loan.outstanding_debt -= max_repayment
            remaining_repayment -= max_repayment
            if loan.outstanding_debt == O:
                self.close_active_loan()

    def close_active_loan(self):
        loan = self.active_loans[0]
        loan.update_duration(self.today)
        self.active_loans.pop(0)
        self.loans_history.append(loan)

    def loan_repayment(self):
        if self.outstanding_debt() > O:
            repayment = Float.min(self.outstanding_debt(), self.marketplace_balance * self.current_repayment_rate)
            self.repay_loans(repayment)
            self.current_cash -= repayment

    def close_all_loans(self):
        for _ in range(len(self.active_loans)):
            self.close_active_loan()

    def calculate_apr(self, duration: Duration) -> Percent:
        apr = (self.interest + 1) ** (constants.YEAR / duration) - 1
        apr = min_max(apr, 0, constants.MAX_APR)
        return apr

    def on_bankruptcy(self):
        self.bankruptcy_date = self.today

    def calculate_results(self):
        self.simulation_results = LoanSimulationResults(
            self.merchant.valuation(self.today, self.net_cashflow()), self.revenue_cagr(), self.inventory_cagr(),
            self.net_cashflow_cagr(), self.valuation_cagr(),
            self.lender_profit(), self.debt_to_loan_amount(self.total_credit), self.debt_to_valuation(),
            self.average_apr(), self.calculate_bankruptcy_rate())

    def calculate_bankruptcy_rate(self) -> Percent:
        if self.bankruptcy_date is None:
            return O
        remaining_duration = self.data_generator.simulated_duration - self.bankruptcy_date + 1
        rate = remaining_duration / self.data_generator.simulated_duration
        return rate

    def duration_until_today(self) -> Duration:
        return self.today - self.data_generator.start_date + 1

    def net_cashflow(self) -> Dollar:
        ncf = self.current_cash - self.outstanding_debt()
        return ncf

    def revenue_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.annual_top_line(self.data_generator.start_date), self.total_revenues,
            self.duration_until_today())
        return cagr

    def inventory_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.inventory_value(self.data_generator.start_date), self.merchant.inventory_value(self.today),
            self.duration_until_today())
        return cagr

    def net_cashflow_cagr(self) -> Percent:
        cagr = calculate_cagr(self.initial_cash, self.net_cashflow(), self.duration_until_today())
        return cagr

    def valuation_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.valuation(self.data_generator.start_date, self.initial_cash),
            self.merchant.valuation(self.today, self.net_cashflow()), self.duration_until_today())
        return cagr

    def is_default(self) -> bool:
        if self.bankruptcy_date is not None:
            return True
        if self.outstanding_debt() == O:
            return False
        if not self.context.duration_based_default:
            return False
        min_remaining_duration = Float.min([loan.remaining_duration(self.today) for loan in self.active_loans])
        return min_remaining_duration == 0

    def loss(self) -> Dollar:
        loss = self.debt_to_loan_amount(self.total_credit) - self.repaid_debt()
        return loss

    def lender_profit(self) -> Dollar:
        if self.total_credit == O:
            return O
        revenues = self.revenue_from_amount(self.debt_to_loan_amount(self.repaid_debt()))
        total_costs = self.loss() + self.cost_of_capital() + self.context.merchant_cost_of_acquisition
        profit = revenues - total_costs
        return profit

    def revenue_from_amount(self, amount: Dollar) -> Dollar:
        return amount * self.interest

    def projected_lender_profit(self) -> Dollar:
        num_loans = 1 if self.total_credit > 0 else self.context.expected_loans_per_year
        cost_of_capital_rate = self.calculate_cost_of_capital_rate(self.context.loan_duration)
        cost_of_capital_per_loan = self.loan_amount() * cost_of_capital_rate
        total_cost_of_capital = cost_of_capital_per_loan * num_loans
        cost_of_acquisition = self.context.merchant_cost_of_acquisition if self.total_credit == O else O
        projected_costs = total_cost_of_capital + cost_of_acquisition
        expected_annual_credit = self.loan_amount() * num_loans
        projected_revenues = self.revenue_from_amount(expected_annual_credit)
        projected_profit = projected_revenues - projected_costs
        return projected_profit

    def projected_remaining_debt(self) -> Dollar:
        if self.outstanding_debt() == O:
            return O
        if self.is_default():
            remaining_debt = self.outstanding_debt()
        else:
            remaining_years = self.remaining_duration() / constants.YEAR
            revenue_in_duration = self.merchant.annual_top_line(self.today) * remaining_years
            repayment_in_duration = revenue_in_duration * self.current_repayment_rate
            remaining_debt = Float.max(O, self.outstanding_debt() - repayment_in_duration)
        return remaining_debt

    def remaining_duration(self) -> Duration:
        if self.context.duration_based_default:
            return max([loan.remaining_duration(self.today) for loan in self.active_loans])
        else:
            return self.context.loan_duration

    def repaid_debt(self) -> Dollar:
        repaid = self.total_credit - self.projected_remaining_debt()
        return repaid

    def calculate_cost_of_capital_rate(self, duration: Duration) -> Percent:
        return inverse_cagr(self.context.cost_of_capital, duration)

    def cost_of_capital(self) -> Dollar:
        for loan in self.active_loans:
            loan.update_duration(self.today)
        loans_for_calculation = self.active_loans + self.loans_history
        cost_of_capital_rates = [self.calculate_cost_of_capital_rate(lh.duration) for lh in loans_for_calculation]
        cost_of_capital_per_loan = [cost_of_capital_rates[i] * loans_for_calculation[i].amount for i in
            range(len(loans_for_calculation))]
        total_cost_of_capital = Float.sum(cost_of_capital_per_loan)
        return total_cost_of_capital

    def debt_to_valuation(self) -> Percent:
        dtv = self.total_credit / self.merchant.valuation(self.today, self.net_cashflow())
        return dtv

    def average_apr(self) -> Percent:
        for loan in self.active_loans:
            loan.update_duration(self.today)
        loans_for_calculation = self.active_loans + self.loans_history
        all_apr = [self.calculate_apr(loan.duration) for loan in loans_for_calculation]
        all_amounts = [loan.amount for loan in loans_for_calculation]
        apr = weighted_average(all_apr, all_amounts)
        return apr


class IncreasingRebateLoanSimulation(LoanSimulation):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(IncreasingRebateLoanSimulation, self).__init__(context, data_generator, merchant)

    def calculate_repayment_rate(self) -> Percent:
        if self.today > self.context.loan_duration:
            return self.default_repayment_rate() + self.context.delayed_loan_repayment_increase
        return self.default_repayment_rate()


class NoCapitalLoanSimulation(LoanSimulation):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(NoCapitalLoanSimulation, self).__init__(context, data_generator, merchant)

    def add_debt(self, amount: Dollar):
        pass

    def loan_amount(self) -> Dollar:
        return O
