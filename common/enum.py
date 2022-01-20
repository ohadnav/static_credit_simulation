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
    REVENUE_CAGR = 0
    TOTAL_INTEREST = 1
