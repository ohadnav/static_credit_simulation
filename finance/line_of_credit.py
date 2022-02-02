from common.local_numbers import Float, Dollar, O
from common.util import min_max
from finance.loan_simulation import LoanSimulation
from finance.underwriting import Underwriting


class LineOfCreditSimulation(LoanSimulation):
    def remaining_credit(self) -> Dollar:
        return Float.max(O, self.approved_amount() - self.debt_to_loan_amount(self.ledger.outstanding_balance()))

    def secondary_approval_conditions(self):
        return True

    def calculate_amount(self) -> Dollar:
        amount = Float.min(
            self.credit_needed(), self.remaining_credit(), super(LineOfCreditSimulation, self).calculate_amount())
        return amount


class DynamicLineOfCreditSimulation(LineOfCreditSimulation):
    def update_repayment_rate(self):
        if self.underwriting.approved(self.merchant, self.today):
            risk_context = self.underwriting.calculate_score(self.merchant, self.today)
            repayment_ratio = self.context.agg_score_benchmark / Underwriting.aggregated_score(risk_context)
            new_rate = (repayment_ratio ** self.context.repayment_factor) * self.default_repayment_rate()
            new_rate = min_max(new_rate, self.context.min_repayment_rate, self.context.max_repayment_rate)
            self.current_repayment_rate = new_rate
        elif self.context.revenue_collateralization:
            self.current_repayment_rate = self.context.max_repayment_rate
        else:
            self.current_repayment_rate = self.default_repayment_rate()


class InvoiceFinancingSimulation(LineOfCreditSimulation):
    def approved_amount(self) -> Dollar:
        # TODO: risk-based-pricing
        batches = self.merchant.batches_with_orders(self.today)
        approved_batches_cost = O
        for batch in batches:
            if self.underwriting.approved(batch, self.today):
                approved_batches_cost += batch.max_cash_needed(self.today)
        approved_amount = Float.min(approved_batches_cost, self.loan_amount())
        return approved_amount
