from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional, List

from local_enum import LoanSimulationType, LoanReferenceType
from merchant_factory import Condition


@dataclass(unsafe_hash=True)
class Scenario:
    conditions: Optional[List[Condition]] = None
    volatile: bool = False
    loan_simulation_types: Optional[List[LoanSimulationType]] = None
    loan_reference_type: Optional[LoanReferenceType] = None

    def __str__(self):
        to_join = []
        to_join.append('Volatile' if self.volatile else '')
        to_join.append(self.loan_reference_type.name if self.loan_reference_type else '')
        if self.conditions:
            to_join.extend([condition.__str__() for condition in self.conditions])
        return ' '.join(filter(None, to_join))

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def generate_scenario_variants(
            scenario: Scenario, loan_types: List[LoanSimulationType], include_base_scenario: bool) -> List[Scenario]:
        assert scenario.loan_reference_type is None
        scenario.loan_simulation_types = loan_types
        scenarios = [scenario] if include_base_scenario else []
        for loan_reference_type in LoanReferenceType.list():
            reference_scenario = deepcopy(scenario)
            reference_scenario.loan_reference_type = loan_reference_type
            reference_scenario.loan_simulation_types = loan_types
            if not reference_scenario.conditions:
                reference_scenario.conditions = []
            for loan_type in loan_types:
                reference_scenario.conditions.append(
                    Condition.generate_from_loan_reference_type(loan_reference_type, loan_type))
            scenarios.append(reference_scenario)
        return scenarios

    def get_dir(self, run_dir: str, to_make: bool = False) -> str:
        scenario_dir = f'{run_dir}/{self.__str__()}'
        if to_make:
            os.mkdir(scenario_dir)
        return scenario_dir
