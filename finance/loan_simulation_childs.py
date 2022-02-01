from __future__ import annotations

from loan_simulation import LoanSimulation
from local_numbers import Dollar, O


class IncreasingRebateLoanSimulation(LoanSimulation):
    def update_repayment_rate(self):
        if self.ledger.active_loans and self.today >= self.ledger.get_current_loan().start_date + \
                self.context.loan_duration:
            self.current_repayment_rate = self.default_repayment_rate() + self.context.delayed_loan_repayment_increase
        else:
            self.current_repayment_rate = self.default_repayment_rate()


class NoCapitalLoanSimulation(LoanSimulation):
    def add_debt(self, amount: Dollar):
        pass

    def loan_amount(self) -> Dollar:
        return O
