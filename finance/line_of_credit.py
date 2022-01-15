from common import constants
from common.context import SimulationContext, DataGenerator
from common.util import min_max, Dollar, O, Float
from finance.loan_simulation import LoanSimulation
from seller.merchant import Merchant


class LineOfCreditSimulation(LoanSimulation):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(LineOfCreditSimulation, self).__init__(context, data_generator, merchant)

    def remaining_credit(self) -> Dollar:
        return Float.max(O, self.approved_amount() - self.debt_to_loan_amount(self.outstanding_debt()))

    def should_take_loan(self) -> bool:
        return self.credit_needed() > O

    def calculate_amount(self) -> Dollar:
        amount = Float.min(self.credit_needed(), self.remaining_credit())
        return amount


class DynamicLineOfCreditSimulation(LineOfCreditSimulation):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(DynamicLineOfCreditSimulation, self).__init__(context, data_generator, merchant)

    def update_credit(self):
        super(DynamicLineOfCreditSimulation, self).update_credit()
        self.update_repayment_rate()

    def update_repayment_rate(self):
        if self.underwriting.approved(self.today):
            repayment_ratio = self.context.repayment_factor / self.underwriting.aggregated_score()
            new_rate = (repayment_ratio ** 2) * self.default_repayment_rate()
            new_rate = min_max(new_rate, constants.MIN_REPAYMENT_RATE, constants.MAX_REPAYMENT_RATE)
            self.current_repayment_rate = new_rate
        elif self.context.revenue_collateralization:
            self.current_repayment_rate = constants.MAX_REPAYMENT_RATE
        else:
            self.current_repayment_rate = self.default_repayment_rate()
