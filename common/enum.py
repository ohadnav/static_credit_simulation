from __future__ import annotations

from enum import Enum
from typing import List


class ExtendedEnum(Enum):
    @classmethod
    def list(cls) -> List[LoanSimulationType]:
        return list(map(lambda c: c, cls))


class LoanSimulationType(ExtendedEnum):
    DEFAULT = 'LoanSimulation'
    INCREASING_REBATE = 'IncreasingRebateLoanSimulation'
    LINE_OF_CREDIT = 'LineOfCreditSimulation'
    DYNAMIC_LINE_OF_CREDIT = 'DynamicLineOfCreditSimulation'
    NO_CAPITAL = 'NoCapitalLoanSimulation'


class LoanReferenceType(ExtendedEnum):
    EQUAL_GROWTH = 0
