from autologging import traced, logged

from common import constants
from common.context import SimulationContext, DataGenerator
from common.util import min_max, Dollar
from finance.loan import Loan
from seller.merchant import Merchant


@traced
@logged
class LineOfCredit(Loan):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(LineOfCredit, self).__init__(context, data_generator, merchant)

    def remaining_credit(self) -> Dollar:
        return self.approved_amount() - self.debt_to_loan_amount(self.outstanding_debt)

    def update_credit(self):
        max_credit = min(self.credit_needed(), self.remaining_credit())
        self.add_debt(max_credit)


@traced
@logged
class DynamicLineOfCredit(LineOfCredit):
    def __init__(self, context: SimulationContext, data_generator: DataGenerator, merchant: Merchant):
        super(DynamicLineOfCredit, self).__init__(context, data_generator, merchant)

    def update_credit(self):
        super(DynamicLineOfCredit, self).update_credit()
        self.update_repayment_rate()

    def update_repayment_rate(self):
        if self.underwriting.approved(self.today):
            repayment_ratio = constants.REPAYMENT_FACTOR / self.underwriting.aggregated_score()
            # repayment_ratio = constants.REPAYMENT_FACTOR / self.underwriting.benchmark_score(
            #     'debt_to_inventory', self.today)
            new_rate = repayment_ratio * self.default_repayment_rate()
            new_rate = min_max(new_rate, constants.MIN_REPAYMENT_RATE, constants.MAX_REPAYMENT_RATE)
            self.current_repayment_rate = new_rate
        elif self.context.revenue_collateralization:
            self.current_repayment_rate = constants.MAX_REPAYMENT_RATE
        else:
            self.current_repayment_rate = self.default_repayment_rate()
