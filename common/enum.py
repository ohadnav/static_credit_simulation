from __future__ import annotations

from enum import Enum
from typing import List


class ExtendedEnum(Enum):
    @classmethod
    def list(cls) -> List:
        return list(map(lambda c: c, cls))


class LoanSimulationType(ExtendedEnum):
    DEFAULT = 'LoanSimulation'
    INCREASING_REBATE = 'IncreasingRebateLoanSimulation'
    LINE_OF_CREDIT = 'LineOfCreditSimulation'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCreditSimulation'
    NO_CAPITAL = 'NoCapitalLoanSimulation'


class LoanReferenceType(ExtendedEnum):
    TOTAL_INTEREST = 1
    TOTAL_REVENUE = 2
    REVENUE_CAGR = 3
