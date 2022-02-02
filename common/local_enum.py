from __future__ import annotations

from enum import Enum
from typing import List


class ExtendedEnum(Enum):
    @classmethod
    def list(cls) -> List:
        return list(map(lambda c: c, cls))

    def __eq__(self, other):
        if type(other).__name__ != type(self).__name__:
            return False
        return self.value == other.value

    def __hash__(self):
        return hash(self.name)


class LoanSimulationType(ExtendedEnum):
    INCREASING_REBATE = 'IncreasingRebateLoanSimulation'
    INVOICE_FINANCING = 'InvoiceFinancingSimulation'
    LINE_OF_CREDIT = 'LineOfCreditSimulation'
    DEFAULT = 'LoanSimulation'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCreditSimulation'
    NO_CAPITAL = 'NoCapitalLoanSimulation'


class RuntimeType(ExtendedEnum):
    RUN_ALL = 'RunAll'
    BENCHMARK_SIMULATION = 'BenchmarkSimulation'
    PLOT_TIMELINE = 'TimelineSimulation'


class LoanReferenceType(ExtendedEnum):
    TOTAL_INTEREST = 1
    ANNUAL_REVENUE = 2
    DAILY_REVENUE = 3
    REVENUE_CAGR = 4
