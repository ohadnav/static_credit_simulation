from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import List, MutableMapping, Optional

from common.context import DataGenerator, SimulationContext
from common.numbers import Dollar, Date, Duration, Float, O_INT, O, Int
from common.primitive import Primitive


@dataclass(unsafe_hash=True)
class Loan:
    amount: Dollar
    outstanding_balance: Dollar
    start_date: Date

    @staticmethod
    def current_loan(loans: List[Loan]):
        return loans[0]


@dataclass(unsafe_hash=True)
class Repayment:
    day: Date
    amount: Dollar
    duration: Duration

    @classmethod
    def generate_from_loan(cls, repayment_date: Date, loan: Loan, amount: Dollar) -> Repayment:
        assert repayment_date >= loan.start_date
        duration = repayment_date.from_date(loan.start_date)
        repayment = Repayment(repayment_date, amount, duration)
        return repayment

    def repay(self, loans: List[Loan]):
        Loan.current_loan(loans).outstanding_balance -= self.amount
        if Loan.current_loan(loans).outstanding_balance == O:
            loans.pop(0)


class Ledger(Primitive):
    def __init__(self, data_generator: DataGenerator, context: SimulationContext):
        super(Ledger, self).__init__(data_generator)
        self.context = context
        self.active_loans: List[Loan] = []
        self.loans_history: List[Loan] = []
        self.repayments: List[Repayment] = []
        self.cash_history: MutableMapping[Date, Dollar] = {}
        self.paid_balance = O

    def total_credit(self) -> Dollar:
        return Float.sum([loan.amount for loan in self.loans_history])

    def get_num_loans(self) -> Int:
        return Int(len(self.loans_history))

    def get_current_loan(self) -> Loan:
        return Loan.current_loan(self.active_loans)

    def new_loan(self, loan: Loan):
        self.active_loans.append(loan)
        self.loans_history.append(deepcopy(loan))

    def record_cash(self, day: Date, amount: Dollar):
        self.cash_history[day] = amount

    def outstanding_balance(self, loans: Optional[List[Loan]] = None) -> Dollar:
        if loans is None:
            return self.outstanding_balance(self.active_loans) if self.active_loans else O
        return Float.sum([loan.outstanding_balance for loan in loans])

    def repayments_from_amount(self, repayment_date: Date, total_amount: Dollar, loans: Optional[List[Loan]] = None) \
            -> \
                    List[Repayment]:
        loans = loans or self.active_loans
        remaining_amount = total_amount
        repayments: List[Repayment] = []
        while remaining_amount > O and loans:
            repayment_amount = Float.min(Loan.current_loan(loans).outstanding_balance, remaining_amount)
            remaining_amount -= repayment_amount
            repayment = Repayment.generate_from_loan(repayment_date, Loan.current_loan(loans), repayment_amount)
            repayments.append(repayment)
            repayment.repay(loans)
        return repayments

    def initiate_loan_repayment(self, today: Date, max_amount: Dollar):
        actual_amount = Float.min(self.outstanding_balance(), max_amount)
        new_repayments = self.repayments_from_amount(today, actual_amount)
        self.repayments.extend(new_repayments)
        self.paid_balance += actual_amount

    def projected_repayments(
            self, projected_remaining_debt: Dollar, today: Date, projected_amount_per_repayment: Dollar) -> List[
        Repayment]:
        projected_total_repaid_amount = self.outstanding_balance() - projected_remaining_debt
        repayments: List[Repayment] = []
        if projected_amount_per_repayment == O or projected_total_repaid_amount == O:
            return repayments
        remaining_amount = projected_total_repaid_amount
        projected_loans = deepcopy(self.active_loans)
        date = today + self.context.marketplace_payment_cycle - 1
        while remaining_amount > O and projected_loans and date - today < self.context.loan_duration:
            actual_amount = Float.min(
                [self.outstanding_balance(projected_loans), remaining_amount, projected_amount_per_repayment])
            repayments.extend(self.repayments_from_amount(date, actual_amount, projected_loans))
            remaining_amount -= actual_amount
            date += self.context.marketplace_payment_cycle
        return repayments

    def remaining_loan_duration(self, today: Date, loan: Loan) -> Duration:
        duration = loan.start_date + self.context.loan_duration - today
        return Duration.max(duration, O_INT)

    def remaining_durations(self, today: Date) -> List[Duration]:
        return [self.remaining_loan_duration(today, loan) for loan in self.active_loans]

    def undo_active_loans(self):
        adjustment = 0
        for i in range(len(self.active_loans)):
            history_index = -1 - i + adjustment
            if self.active_loans[-1].outstanding_balance == self.loans_history[history_index].outstanding_balance:
                adjustment += 1
                self.loans_history.pop()
            else:
                remaining_rate = 1 - self.active_loans[-1].outstanding_balance / self.loans_history[
                    history_index].outstanding_balance
                self.loans_history[history_index].outstanding_balance = self.active_loans[-1].outstanding_balance
                self.loans_history[history_index].amount -= remaining_rate * self.active_loans[-1].amount
            self.active_loans.pop()
