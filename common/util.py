import math
from typing import Union, List

from common import constants

Percent = float
Date = int
Duration = int
Stock = int
Dollar = float


def calculate_cagr(first_value: float, last_value: float, duration: Duration) -> Percent:
    if last_value == 0:
        return float('-inf') if first_value > 0 else 0
    math.pow(first_value / last_value - 1, duration / constants.YEAR)


def min_max(value: Union[float, int], min_value: Union[float, int], max_value: Union[float, int]) -> Union[float, int]:
    value = max(min_value, value)
    value = min(max_value, value)
    return value


def weighted_average(values: List[float], weights: List[float]):
    assert len(values) == len(weights)
    weighted_values = sum([values[i] * weights[i] for i in range(len(values))])
    total_weights = sum([weights[i] for i in range(len(weights))])
    if total_weights == 0:
        return 0
    return weighted_values / total_weights