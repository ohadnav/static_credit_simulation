from __future__ import annotations

import inspect
from typing import Union, List, Optional, TypeVar, Mapping

from common import constants
from common.local_numbers import Float, Percent, Duration, O, ONE, Int

T = TypeVar('T')
S = TypeVar('S')


def get_key_from_value(value_to_look_for: T, dictionary: Mapping[S, T]) -> S:
    for key, value in dictionary.items():
        if value == value_to_look_for:
            return key
    raise KeyError()


def calculate_cagr(first_value: Float, last_value: Float, duration: Duration) -> Optional[Percent]:
    if first_value <= O:
        if last_value <= O:
            return O
        else:
            return ONE
    elif last_value <= O:
        return Float(-1)
    return (last_value / first_value) ** (constants.YEAR / duration) - ONE


def inverse_cagr(cagr: Percent, duration: Duration) -> Optional[Percent]:
    if cagr <= O:
        return Float(-1)
    return (1 + cagr) ** (duration / constants.YEAR) - 1


NUMERIC_TYPES = Union[float, int, Int, Duration, Float]


def min_max(value: NUMERIC_TYPES, min_value: NUMERIC_TYPES, max_value: NUMERIC_TYPES) -> NUMERIC_TYPES:
    if isinstance(value, int):
        value = Int.max(min_value, value)
        value = Int.min(max_value, value)
        if isinstance(value, Duration):
            value = Duration(value)
    else:
        value = Float.max(min_value, value)
        value = Float.min(max_value, value)
    return value


def weighted_average(values: List[float], weights: List[float]) -> Float:
    assert len(values) == len(weights)
    weighted_values = Float.sum([values[i] * weights[i] for i in range(len(values))])
    total_weights = Float.sum([weights[i] for i in range(len(weights))])
    if total_weights == O:
        return O
    return weighted_values / total_weights


# noinspection PyRedeclaration


def shout_print(msg: str):
    print(f'\n\n{"*" * len(msg)}\n')
    print(msg)
    print(f'\n{"*" * len(msg)}')


def flatten(_list: List):
    return [item for sublist in _list for item in sublist]


def inherits_from(child, parent_name):
    if inspect.isclass(child):
        if parent_name in [c.__name__ for c in inspect.getmro(child)[1:]]:
            return True
    return False


def intersection(list1: List, list2: List) -> List:
    intersection_list = [value for value in list1 if value in list2]
    return intersection_list
