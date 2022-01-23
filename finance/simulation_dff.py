from typing import Mapping

from common.numbers import O, Date
from finance.loan_simulation import LoanSimulation

LEDGER_ATTRIBUTES = ['loans_history', 'active_loans', 'repayments']
MERCHANT_ATTRIBUTES = ['roas', 'inventory_turnover_ratio', 'adjusted_profit_margin', 'profit_margin',
    'out_of_stock_rate',
    'organic_rate', 'inventory_value', 'annual_top_line', 'max_cash_needed',
    'revenue_per_day', 'gp_per_day']


class LoanSimulationDiff:
    def __init__(self, loan1: LoanSimulation, loan2: LoanSimulation):
        self.diff = {}
        self.loan1 = loan1
        self.loan2 = loan2

    def get_diff(self) -> Mapping:
        self.calculate_diff()
        return self.diff

    def calculate_diff(self):
        self.merchant_diff()
        self.today_diff()
        self.ledger_diff()

    def today_diff(self):
        if self.loan1.today != self.loan2.today:
            self.diff['today'] = self.loan1.today - self.loan2.today

    def ledger_diff(self):
        self.diff['ledger'] = {}
        for attribute in LEDGER_ATTRIBUTES:
            self.ledger_attribute_diff(attribute)
        self.ledger_cash_history_diff()
        if not self.diff['ledger']:
            del self.diff['ledger']

    def merchant_diff(self):
        self.diff['merchant'] = {}
        for attribute in MERCHANT_ATTRIBUTES:
            self.merchant_attribute_diff(attribute)
        self.merchant_stock_diff()
        if not self.diff['merchant']:
            del self.diff['merchant']

    def ledger_cash_history_diff(self):
        self.diff['ledger']['cash_history'] = {}
        last_day1 = self.loan1.data_generator.start_date
        last_day2 = self.loan2.data_generator.start_date
        for day in range(self.loan1.data_generator.start_date, min(self.loan1.today, self.loan2.today) + 1):
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

    def ledger_attribute_diff(self, attribute: str):
        self.diff['ledger'][attribute] = []
        ledger_list1 = getattr(self.loan1.ledger, attribute)
        ledger_list2 = getattr(self.loan2.ledger, attribute)
        for i in range(min(len(ledger_list1), len(ledger_list2))):
            if ledger_list1[i] != ledger_list2[i]:
                self.diff['ledger'][attribute].append((ledger_list1[i], ledger_list2[i]))
        for i in range(min(len(ledger_list1), len(ledger_list2)), max(len(ledger_list1), len(ledger_list2))):
            self.diff['ledger'][attribute].append(
                (
                    ledger_list1[i] if i < len(ledger_list1) else None,
                    ledger_list2[i] if i < len(ledger_list2) else None))
        if not self.diff['ledger'][attribute]:
            del self.diff['ledger'][attribute]

    def merchant_stock_diff(self):
        self.diff['merchant']['stock'] = {}
        for i in range(len(self.loan1.merchant.inventories)):
            self.diff['merchant']['stock'][i] = {}
            for j in range(len(self.loan1.merchant.inventories[i].batches)):
                batch1 = self.loan1.merchant.inventories[i].batches[j]
                batch2 = self.loan2.merchant.inventories[i].batches[j]
                if batch1.stock != batch2.stock:
                    self.diff['merchant']['stock'][i] = (j, batch1.stock - batch2.stock)
            if not self.diff['merchant']['stock'][i]:
                del self.diff['merchant']['stock'][i]
        if not self.diff['merchant']['stock']:
            del self.diff['merchant']['stock']

    def merchant_attribute_diff(self, attribute: str):
        self.diff['merchant'][attribute] = {}
        for day in range(self.loan1.data_generator.start_date, min(self.loan1.today, self.loan2.today) + 1):
            day = Date(day)
            value1 = getattr(self.loan1.merchant, attribute)(day)
            value2 = getattr(self.loan2.merchant, attribute)(day)
            if value1 != value2:
                self.diff['merchant'][attribute][day] = value1 - value2
        if not self.diff['merchant'][attribute]:
            del self.diff['merchant'][attribute]
