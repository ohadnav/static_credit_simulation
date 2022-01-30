from dataclasses import dataclass, fields
from typing import Mapping

from common.context import SimulationContext, DataGenerator
from common.numbers import O, Date
from finance.ledger import Ledger
from finance.loan_simulation_results import LoanSimulationResults
from seller.merchant import Merchant

MERCHANT_ATTRIBUTES = ['get_roas', 'get_inventory_turnover_ratio', 'get_adjusted_profit_margin', 'profit_margin',
    'get_out_of_stock_rate',
    'get_organic_rate', 'inventory_value', 'annual_top_line', 'max_cash_needed',
    'revenue_per_day', 'gp_per_day']


@dataclass
class LoanDataContainer:
    ledger: Ledger
    merchant: Merchant
    results: LoanSimulationResults


class LoanSimulationDiff:
    def __init__(
            self, data_generator: DataGenerator, context: SimulationContext, loan1: LoanDataContainer,
            loan2: LoanDataContainer):
        self.diff = {}
        self.loan1 = loan1
        self.loan2 = loan2
        self.data_generator = data_generator
        self.context = context

    def calculate_diff(self, today1: Date, today2: Date) -> Mapping:
        self.merchant_diff(today1, today2)
        self.ledger_diff(today1, today2)
        self.results_diff()
        self.today_diff(today1, today2)
        return self.diff

    def fast_diff(self, today1: Date, today2: Date) -> bool:
        min_today = Date(min(today1, today2))
        for i in range(len(self.loan1.ledger.loans_history)):
            if i >= len(self.loan2.ledger.loans_history):
                return True
            if self.loan1.ledger.loans_history[i].start_date > min_today:
                if self.loan2.ledger.loans_history[i].start_date < min_today:
                    return True
                else:
                    break
            if self.loan1.ledger.loans_history[i] != self.loan2.ledger.loans_history[i]:
                return True
        return False

    def today_diff(self, today1: Date, today2: Date):
        if today1 != today2:
            self.diff['today'] = today1 - today2

    def results_diff(self):
        self.diff['results'] = {}
        for field in fields(self.loan1.results):
            value1 = getattr(self.loan1.results, field.name)
            value2 = getattr(self.loan2.results, field.name)
            if value1 != value2:
                self.diff['results'][field.name] = value1 - value2
        if not self.diff['results']:
            del self.diff['results']

    def ledger_diff(self, today1: Date, today2: Date):
        self.diff['ledger'] = {}
        self.ledger_loans_history_diff()
        self.ledger_repayments_diff(today1, today2)
        self.ledger_cash_history_diff(today1, today2)
        if not self.diff['ledger']:
            del self.diff['ledger']

    def merchant_diff(self, today1: Date, today2: Date):
        self.diff['merchant'] = {}
        for attribute in MERCHANT_ATTRIBUTES:
            self.merchant_attribute_diff(attribute, today1, today2)
        self.merchant_stock_diff(today1, today2)
        if not self.diff['merchant']:
            del self.diff['merchant']

    def ledger_cash_history_diff(self, today1: Date, today2: Date):
        self.diff['ledger']['cash_history'] = {}
        last_day1 = self.data_generator.start_date
        last_day2 = self.data_generator.start_date
        for day in range(self.data_generator.start_date, min(today1, today2) + 1):
            day = Date(day)
            last_day1 = day if day in self.loan1.ledger.cash_history else last_day1
            last_day2 = day if day in self.loan2.ledger.cash_history else last_day2
            if self.loan1.ledger.cash_history[last_day1] - self.loan2.ledger.cash_history[last_day2] != O:
                if day in self.loan1.ledger.cash_history or day in self.loan2.ledger.cash_history:
                    self.diff['ledger']['cash_history'][day] = self.loan1.ledger.cash_history[last_day1] - \
                                                               self.loan2.ledger.cash_history[
                                                                   last_day2]
        if not self.diff['ledger']['cash_history']:
            del self.diff['ledger']['cash_history']

    def ledger_repayments_diff(self, today1: Date, today2: Date):
        if len(self.loan1.ledger.repayments) == 0 or len(self.loan2.ledger.repayments) == 0:
            return
        self.diff['ledger']['repayments'] = {}
        i1 = 0
        i2 = 0
        for day in range(
                self.context.marketplace_payment_cycle, min(today1, today2) + 1,
                self.context.marketplace_payment_cycle):
            day = Date(day)
            if day > self.loan1.ledger.repayments[i1].day:
                i1 += 1
            if day > self.loan2.ledger.repayments[i2].day:
                i2 += 1
            if i1 >= len(self.loan1.ledger.repayments) or i2 >= len(self.loan2.ledger.repayments):
                break
            if day in [self.loan1.ledger.repayments[i1].day, self.loan2.ledger.repayments[i2].day]:
                repay1 = self.loan1.ledger.repayments[i1].amount if day == self.loan1.ledger.repayments[i1].day else O
                repay2 = self.loan2.ledger.repayments[i2].amount if day == self.loan2.ledger.repayments[i2].day else O
                repay_gap = repay1 - repay2
                if repay_gap != O:
                    self.diff['ledger']['repayments'][day] = repay_gap
        if not self.diff['ledger']['repayments']:
            del self.diff['ledger']['repayments']

    def ledger_loans_history_diff(self):
        self.diff['ledger']['loans_history'] = []
        for i in range(min(len(self.loan1.ledger.loans_history), len(self.loan2.ledger.loans_history))):
            if self.loan1.ledger.loans_history[i] != self.loan2.ledger.loans_history[i]:
                self.diff['ledger']['loans_history'].append(
                    (self.loan1.ledger.loans_history[i], self.loan2.ledger.loans_history[i]))
        for i in range(
                min(len(self.loan1.ledger.loans_history), len(self.loan2.ledger.loans_history)),
                max(len(self.loan1.ledger.loans_history), len(self.loan2.ledger.loans_history))):
            self.diff['ledger']['loans_history'].append(
                (
                    self.loan1.ledger.loans_history[i] if i < len(self.loan1.ledger.loans_history) else None,
                    self.loan2.ledger.loans_history[i] if i < len(self.loan2.ledger.loans_history) else None))
        if not self.diff['ledger']['loans_history']:
            del self.diff['ledger']['loans_history']

    def merchant_stock_diff(self, today1: Date, today2: Date):
        self.diff['merchant']['stock'] = {}
        for i in range(len(self.loan1.merchant.inventories)):
            self.diff['merchant']['stock'][i] = {}
            for j in range(len(self.loan1.merchant.inventories[i].batches)):
                batch1 = self.loan1.merchant.inventories[i].batches[j]
                batch2 = self.loan2.merchant.inventories[i].batches[j]
                if batch1.stock != batch2.stock and batch1.start_date <= min(today1, today2):
                    self.diff['merchant']['stock'][i] = (j, batch1.stock - batch2.stock, batch1.start_date)
            if not self.diff['merchant']['stock'][i]:
                del self.diff['merchant']['stock'][i]
        if not self.diff['merchant']['stock']:
            del self.diff['merchant']['stock']

    def merchant_attribute_diff(self, attribute: str, today1: Date, today2: Date):
        self.diff['merchant'][attribute] = {}
        last_day = None
        for day in range(self.data_generator.start_date, min(today1, today2) + 1):
            day = Date(day)
            value1 = getattr(self.loan1.merchant, attribute)(day)
            value2 = getattr(self.loan2.merchant, attribute)(day)
            gap = value1 - value2
            if value1 != value2 and (last_day is None or gap != self.diff['merchant'][attribute][last_day]):
                self.diff['merchant'][attribute][day] = gap
                last_day = day
        if not self.diff['merchant'][attribute]:
            del self.diff['merchant'][attribute]
