import math
from copy import deepcopy
from typing import List, Union

from common import constants
from common.context import SimulationContext
from simulation import Simulation


class SensitivitySimulation(Simulation):
    def __init__(self, context: SimulationContext, sensitive_attribute: str):
        self.sensitive_attribute = sensitive_attribute
        self.central_context = context
        assert hasattr(self.central_context, sensitive_attribute)
        sensitivity_contexts = self.generate_sensitivity_contexts()
        super(SensitivitySimulation, self).__init__(sensitivity_contexts)

    def generate_sensitivity_contexts(self) -> List[SimulationContext]:
        sensitivity_contexts = [self.central_context]
        source_value = getattr(self.central_context, self.sensitive_attribute)
        if isinstance(source_value, bool):
            sensitivity_contexts.append(self.generate_context(not source_value))
        else:
            for i in range(1, 11):
                big_value, small_value = SensitivitySimulation.new_values(source_value, i)
                sensitivity_contexts.append(self.generate_context(big_value))
                sensitivity_contexts.insert(0, self.generate_context(small_value))
        return sensitivity_contexts

    @staticmethod
    def new_values(source_value: Union[int, float], degree: int) -> (Union[int, float], Union[int, float]):
        big_change = math.pow(1 + constants.SENSITIVITY, degree)
        small_change = math.pow(1 - constants.SENSITIVITY, degree)
        if isinstance(source_value, int):
            return int(round(source_value * big_change)), int(round(source_value * small_change))
        return round(source_value * big_change), round(source_value * small_change)

    def generate_context(self, new_value: Union[int, float, bool]) -> SimulationContext:
        new_context = deepcopy(self.central_context)
        new_context.name = f'{round(new_value, 2)}_{self.sensitive_attribute}'
        setattr(new_context, self.sensitive_attribute, new_value)
        return new_context