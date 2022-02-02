from __future__ import annotations

from typing import Optional, Mapping, MutableMapping

from common import constants
from common.context import SimulationContext, DataGenerator
from common.local_enum import LoanReferenceType
from common.local_numbers import Float, Percent, Date, Duration, Dollar, O, ONE, O_INT
from common.primitive import Primitive
from common.util import min_max, calculate_cagr, weighted_average, inverse_cagr
from finance.ledger import Ledger, Loan
from finance.loan_simulation_results import LoanSimulationResults
from finance.simulation_dff import LoanSimulationDiff, LoanDataContainer
from finance.underwriting import Underwriting
from seller.merchant import Merchant


class LoanSimulation(Primitive):
    def __init__(
            self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant,
            reference_loan: Optional[LoanSimulation] = None):
        super(LoanSimulation, self).__init__(data_generator)
        self.context = context
        self.merchant = merchant
        self.simulation_results: Optional[LoanSimulationResults] = None
        self.marketplace_balance = O
        self.today = Date(self.data_generator.start_date)
        self.initial_cash = data_generator.initial_cash_ratio * merchant.annual_top_line(self.today)
        self.current_cash = self.initial_cash
        self.bankruptcy_date: Optional[Date] = None
        self.underwriting = Underwriting(self.context, self.data_generator, merchant)
        self.flat_fee = self.context.rbf_flat_fee
        self.last_year_revenue = O
        self.recent_history_revenue = O
        self.current_repayment_rate = self.default_repayment_rate()
        self.ledger = Ledger(self.data_generator, self.context)
        self.ledger.record_cash(self.today, self.initial_cash)
        self.set_reference_loan(reference_loan)
        self.duration_in_debt = Duration(O_INT)
        self.snapshots: MutableMapping[Date, LoanSimulationResults] = {}

    def reset_id(self):
        super(LoanSimulation, self).reset_id()
        self.ledger.reset_id()
        self.merchant.reset_id()

    def set_reference_loan(self, reference_loan: LoanSimulation):
        self.reference_loan = reference_loan
        self.init_loan_reference_diff()

    def estimated_annual_revenue(self) -> Dollar:
        return self.estimated_revenue_over_duration(self.last_year_revenue, constants.YEAR)

    def estimated_revenue_over_duration(self, total_revenue: Dollar, duration: Duration) -> Dollar:
        if self.today <= constants.MONTH:
            return self.merchant.annual_top_line(self.data_generator.start_date) * duration / constants.YEAR
        if self.today <= duration:
            return total_revenue * duration / self.today.from_date(self.data_generator.start_date)
        return total_revenue

    def to_data_container(self) -> LoanDataContainer:
        return LoanDataContainer(self.ledger, self.merchant, self.simulation_results)

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
        self.ledger.new_loan(Loan(amount, new_debt, self.today))
        self.current_cash += amount
        self.record_cash()

    def amount_to_debt(self, amount: Dollar):
        return amount * (1 + self.flat_fee)

    def debt_to_loan_amount(self, debt: Dollar) -> Dollar:
        return debt / (1 + self.flat_fee)

    def max_debt(self) -> Dollar:
        return self.amount_to_debt(self.loan_amount())

    def approved_amount(self) -> Dollar:
        if not self.underwriting.approved(self.merchant, self.today):
            return O
        return self.loan_amount()

    def loan_amount(self) -> Dollar:
        recent_monthly_revenue = self.recent_revenue() * constants.MONTH / \
                                 self.context.history_duration_for_amount_calculation
        amount = recent_monthly_revenue * self.context.loan_amount_per_monthly_income
        amount = Float.min(amount, self.context.max_loan_amount)
        return amount

    def credit_needed(self) -> Dollar:
        buffer = self.merchant.committed_purchase_orders(self.today)
        max_cost_for_growth = self.merchant.max_cash_needed(self.today)
        cash_gap = buffer + max_cost_for_growth - self.current_cash
        return Float.max(O, cash_gap)

    def update_credit(self):
        if self.primary_approval_conditions():
            amount = self.calculate_amount()
            if amount > O:
                self.add_debt(amount)
                self.current_repayment_rate = self.default_repayment_rate()
        self.update_repayment_rate()
        if self.ledger.outstanding_balance() > O:
            self.duration_in_debt += 1

    def update_repayment_rate(self):
        pass

    def close_to_reference_loan(self) -> bool:
        assert self.reference_loan
        value1 = getattr(self, self.context.loan_reference_type.name.lower())()
        value2 = getattr(self.reference_loan, self.context.loan_reference_type.name.lower())()
        return value1.is_close(value2)

    def reference_conditions(self) -> bool:
        if self.reference_loan is None or self.context.loan_reference_type is None:
            return True
        if self.context.loan_reference_type == LoanReferenceType.REVENUE_CAGR:
            if self.revenue_cagr() >= self.reference_loan.revenue_cagr():
                no_diff = not self.loan_reference_diff.fast_diff(self.today, self.reference_loan.today)
                return no_diff
            return True
        elif self.context.loan_reference_type == LoanReferenceType.TOTAL_INTEREST:
            return self.paid_interest() < self.reference_loan.total_interest()
        elif self.context.loan_reference_type == LoanReferenceType.ANNUAL_REVENUE:
            return self.annual_revenue() < self.reference_loan.annual_revenue()
        elif self.context.loan_reference_type == LoanReferenceType.DAILY_REVENUE:
            return self.daily_revenue() < self.reference_loan.daily_revenue()
        assert False

    def daily_revenue(self):
        return self.merchant.revenue_per_day(self.today)

    def annual_revenue(self):
        return self.estimated_annual_revenue()

    def recent_revenue(self) -> Dollar:
        return self.estimated_revenue_over_duration(
            self.recent_history_revenue, self.context.history_duration_for_amount_calculation)

    def calculate_reference_diff(self) -> Mapping:
        return self.loan_reference_diff.calculate_diff(self.today, self.reference_loan.today)

    def init_loan_reference_diff(self):
        if self.reference_loan:
            self.loan_reference_diff = LoanSimulationDiff(
                self.data_generator, self.context, self.to_data_container(), self.reference_loan.to_data_container())

    def primary_approval_conditions(self) -> bool:
        return not self.merchant.is_suspended(
            self.today) and self.projected_lender_profit() >= O and self.secondary_approval_conditions() and \
               self.credit_needed() >= self.context.min_loan_amount and self.reference_conditions()

    def secondary_approval_conditions(self):
        return self.ledger.outstanding_balance() == O

    def calculate_amount(self) -> Dollar:
        amount = self.approved_amount()
        if self.reference_loan and self.context.loan_reference_type == LoanReferenceType.TOTAL_INTEREST:
            remaining_interest = self.reference_loan.total_interest() - self.total_interest()
            remaining_amount = remaining_interest / self.flat_fee
            amount = Float.min(remaining_amount, amount)
        return amount

    def simulate_day(self):
        self.update_credit()
        self.simulate_sales()
        self.marketplace_payout()
        self.simulate_inventory_purchase()
        if self.current_cash < O:
            self.on_bankruptcy()
        self.take_snapshot()

    def take_snapshot(self):
        if self.context.snapshot_cycle and self.today % self.context.snapshot_cycle == 0:
            self.snapshots[self.today] = self.current_simulation_results()

    def simulate_inventory_purchase(self):
        inventory_cost = self.merchant.inventory_cost(self.today, self.current_cash)
        self.current_cash -= inventory_cost
        if inventory_cost > O:
            self.record_cash()

    def record_cash(self):
        self.ledger.record_cash(self.today, self.current_cash)

    def simulate_sales(self):
        self.last_year_revenue += self.merchant.revenue_per_day(self.today)
        self.recent_history_revenue += self.merchant.revenue_per_day(self.today)
        if self.today > constants.YEAR:
            self.last_year_revenue -= self.merchant.revenue_per_day(self.today - constants.YEAR + 1)
        if self.today > self.context.history_duration_for_amount_calculation:
            self.recent_history_revenue -= self.merchant.revenue_per_day(
                self.today - self.context.history_duration_for_amount_calculation + 1)
        self.marketplace_balance += self.merchant.gp_per_day(self.today)

    def marketplace_payout(self):
        if self.today % self.context.marketplace_payment_cycle == 0:
            if self.marketplace_balance == O:
                if not self.merchant.has_future_revenue(self.today):
                    self.on_bankruptcy()
            self.loan_repayment()
            self.current_cash += self.marketplace_balance
            self.record_cash()
            self.marketplace_balance = O

    def loan_repayment(self):
        if self.ledger.outstanding_balance() > O:
            repayment_amount = self.marketplace_balance * self.current_repayment_rate
            self.ledger.initiate_loan_repayment(self.today, repayment_amount)
            self.current_cash -= repayment_amount

    def should_stop_simulation(self) -> bool:
        if self.bankruptcy_date:
            return True
        if self.merchant.annual_top_line(self.today) > self.context.max_merchant_top_line:
            return True
        if not self.reference_conditions():
            return True
        return False

    def simulate(self):
        assert self.today == self.data_generator.start_date
        for i in range(self.data_generator.simulated_duration):
            self.simulate_day()
            if self.should_stop_simulation():
                break
            self.today += Duration(1)
        self.today = Duration.min(self.data_generator.simulated_duration, self.today)
        self.end_simulation()
        self.calculate_results()

    def end_simulation(self):
        if self.bankruptcy_date:
            return
        self.undo_active_loans()

    def undo_active_loans(self):
        amount = self.debt_to_loan_amount(self.ledger.outstanding_balance())
        self.current_cash -= amount
        self.ledger.undo_active_loans()

    def calculate_apr(self, duration: Duration) -> Percent:
        apr = (self.flat_fee + 1) ** (constants.YEAR / duration) - 1
        apr = min_max(apr, 0, constants.MAX_APR)
        return apr

    def on_bankruptcy(self):
        self.bankruptcy_date = self.today

    def calculate_results(self):
        self.simulation_results = self.current_simulation_results()
        self.init_loan_reference_diff()

    def current_simulation_results(self) -> LoanSimulationResults:
        return LoanSimulationResults(
            self.merchant.valuation(self.today, self.net_cashflow()), self.revenue_cagr(), self.annual_revenue(),
            self.recent_revenue(), self.projected_cagr(), self.inventory_cagr(), self.net_cashflow_cagr(),
            self.valuation_cagr(), self.lender_profit(), self.ledger.total_credit(), self.loan_amount(),
            self.ledger.outstanding_balance(),
            self.credit_utilization_rate(), self.credit_needed(), self.remaining_credit(), self.underutilized_credit(),
            self.lender_profit_margin(), self.total_interest(), self.debt_to_valuation(), self.effective_apr(),
            self.bankruptcy_rate(), self.hyper_growth_rate(), self.duration_in_debt_rate(),
            self.duration_finished_rate(), self.ledger.num_loans())

    def remaining_credit(self) -> Dollar:
        return Float.max(O, self.approved_amount() - self.debt_to_loan_amount(self.ledger.outstanding_balance()))

    def underutilized_credit(self) -> Dollar:
        return Float.min(self.credit_needed(), self.remaining_credit())

    def credit_utilization_rate(self) -> Percent:
        if self.loan_amount() <= O:
            return O
        return min_max(self.debt_to_loan_amount(self.ledger.outstanding_balance()) / self.loan_amount(), O, ONE)

    def duration_finished_rate(self) -> Percent:
        return self.today / self.data_generator.simulated_duration

    def duration_in_debt_rate(self) -> Percent:
        return Percent(self.duration_in_debt / self.today)

    def paid_interest(self) -> Dollar:
        return self.interest_from_amount(self.debt_to_loan_amount(self.ledger.paid_balance))

    def total_interest(self) -> Dollar:
        return self.total_debt() - self.ledger.total_credit()

    def total_debt(self) -> Dollar:
        return self.amount_to_debt(self.ledger.total_credit())

    def bankruptcy_rate(self) -> Percent:
        if self.bankruptcy_date is None:
            return O
        remaining_duration = self.data_generator.simulated_duration.from_date(self.bankruptcy_date)
        rate = remaining_duration / self.data_generator.simulated_duration
        return rate

    def hyper_growth_rate(self) -> Percent:
        revenue_cagr = self.projected_cagr()
        if revenue_cagr < 10:
            return O
        return ONE

    def duration_until_today(self) -> Duration:
        return self.today.from_date(self.data_generator.start_date)

    def net_cashflow(self) -> Dollar:
        ncf = self.current_cash - self.ledger.outstanding_balance()
        return ncf

    def projected_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.annual_top_line(self.data_generator.start_date), self.merchant.annual_top_line(self.today),
            self.duration_until_today())
        return cagr

    def revenue_cagr(self) -> Percent:
        cagr = calculate_cagr(
            self.merchant.annual_top_line(self.data_generator.start_date), self.estimated_annual_revenue(),
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
        if self.ledger.outstanding_balance() == O:
            return False
        if not self.context.duration_based_default:
            return False
        min_remaining_duration = Float.min(self.ledger.remaining_durations(self.today))
        return min_remaining_duration == 0

    def loss(self) -> Dollar:
        loss = Float.max(self.ledger.total_credit() - self.repaid_debt(), O)
        return loss

    def lender_profit(self) -> Dollar:
        if self.ledger.total_credit() == O:
            return O
        revenues = self.interest_from_amount(self.debt_to_loan_amount(self.repaid_debt()))
        total_costs = self.loss() + self.cost_of_capital() + self.operating_costs() + \
                      self.context.merchant_cost_of_acquisition
        profit = revenues - total_costs
        return profit

    def lender_profit_margin(self) -> Percent:
        profit = self.lender_profit()
        total_credit = self.ledger.total_credit()
        if total_credit == O or profit <= O:
            return O
        margin = profit / total_credit
        return margin

    def interest_from_amount(self, amount: Dollar) -> Dollar:
        return amount * self.flat_fee

    def projected_lender_profit(self) -> Dollar:
        num_loans = 1 if self.ledger.total_credit() > 0 else self.context.expected_loans_per_year
        cost_of_capital_rate = self.calculate_cost_of_capital_rate(self.context.loan_duration)
        cost_of_capital_per_loan = self.loan_amount() * cost_of_capital_rate
        total_cost_of_capital = cost_of_capital_per_loan * num_loans
        cost_of_acquisition = self.context.merchant_cost_of_acquisition if self.ledger.total_credit() == O else O
        operating_costs = self.context.operating_cost_per_loan * num_loans
        projected_costs = total_cost_of_capital + cost_of_acquisition + operating_costs
        expected_credit = self.loan_amount() * num_loans
        projected_revenues = self.interest_from_amount(expected_credit)
        projected_profit = projected_revenues - projected_costs
        return projected_profit

    def projected_remaining_debt(self) -> Dollar:
        if self.ledger.outstanding_balance() == O:
            return O
        if self.is_default():
            remaining_debt = self.ledger.outstanding_balance()
        else:
            remaining_years = self.remaining_duration() / constants.YEAR
            revenue_in_duration = self.merchant.annual_top_line(self.today) * remaining_years
            repayment_in_duration = revenue_in_duration * self.current_repayment_rate
            remaining_debt = Float.max(O, self.ledger.outstanding_balance() - repayment_in_duration)
        return remaining_debt

    def remaining_duration(self) -> Duration:
        if self.context.duration_based_default:
            return Duration.max(self.ledger.remaining_durations(self.today))
        else:
            return self.context.loan_duration

    def repaid_debt(self) -> Dollar:
        repaid = self.total_debt() - self.projected_remaining_debt()
        return repaid

    def calculate_cost_of_capital_rate(self, duration: Duration) -> Percent:
        return Percent(inverse_cagr(self.context.cost_of_capital, duration))

    def operating_costs(self) -> Dollar:
        return self.context.operating_cost_per_loan * self.ledger.num_loans()

    def projected_amount_per_repayment(self) -> Dollar:
        average_payout = self.context.marketplace_payment_cycle * self.merchant.gp_per_day(self.today)
        repayment_amount = average_payout * self.current_repayment_rate
        return repayment_amount

    def cost_of_capital(self) -> Dollar:
        repayments_for_calculation = self.repayments_for_results()
        cost_of_capital_rates = [self.calculate_cost_of_capital_rate(repayment.duration) for repayment in
            repayments_for_calculation]
        cost_of_capital_per_loan = [
            cost_of_capital_rates[i] * self.debt_to_loan_amount(repayments_for_calculation[i].amount) for i in
            range(len(repayments_for_calculation))]
        total_cost_of_capital = Float.sum(cost_of_capital_per_loan)
        return total_cost_of_capital

    def debt_to_valuation(self) -> Percent:
        dtv = self.total_debt() / self.merchant.valuation(self.today, self.net_cashflow())
        return dtv

    def effective_apr(self) -> Percent:
        repayments_for_calculation = self.repayments_for_results()
        all_apr = [self.calculate_apr(repayment.duration) for repayment in repayments_for_calculation]
        all_amounts = [loan.amount for loan in repayments_for_calculation]
        apr = weighted_average(all_apr, all_amounts)
        return apr

    def repayments_for_results(self):
        return self.ledger.projected_repayments(
            self.projected_remaining_debt(), self.today, self.projected_amount_per_repayment()) + self.ledger.repayments
