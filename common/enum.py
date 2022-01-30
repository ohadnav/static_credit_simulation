from __future__ import annotations

from enum import Enum
from typing import List


class ExtendedEnum(Enum):
    @classmethod
    def list(cls) -> List:
        return list(map(lambda c: c, cls))


class LoanSimulationType(ExtendedEnum):
    INCREASING_REBATE = 'IncreasingRebateLoanSimulation'
    INVOICE_FINANCING = 'InvoiceFinancingSimulation'
    LINE_OF_CREDIT = 'LineOfCreditSimulation'
    DEFAULT = 'LoanSimulation'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCreditSimulation'
    NO_CAPITAL = 'NoCapitalLoanSimulation'


class LoanReferenceType(ExtendedEnum):
    TOTAL_INTEREST = 1
    DAILY_REVENUE = 2
    TOTAL_REVENUE = 3
    REVENUE_CAGR = 4
