from __future__ import annotations

import math
import multiprocessing
from typing import Union, List, Optional, Iterable

from joblib import Parallel
from tqdm.auto import tqdm

from common import constants


class Float(float):
    def __eq__(self, other):
        if math.isclose(self, other, abs_tol=constants.FLOAT_ADJUSTMENT, rel_tol=constants.FLOAT_ADJUSTMENT):
            return True
        return super(Float, self).__eq__(other)

    def __hash__(self):
        return super(Float, self).__hash__()

    def __lt__(self, other) -> bool:
        if self == other:
            return False
        return super(Float, self).__lt__(other)

    def __le__(self, other) -> bool:
        if self == other:
            return True
        return super(Float, self).__le__(other)

    def __gt__(self, other) -> bool:
        if self == other:
            return False
        return super(Float, self).__gt__(other)

    def __ge__(self, other) -> bool:
        if self == other:
            return True
        return super(Float, self).__ge__(other)

    def __add__(self, other) -> Float:
        return Float(super(Float, self).__add__(other))

    def __mul__(self, other) -> Float:
        return Float(super(Float, self).__mul__(other))

    def __sub__(self, other) -> Float:
        return Float(super(Float, self).__sub__(other))

    def __truediv__(self, other) -> Float:
        return Float(super(Float, self).__truediv__(other))

    def __pow__(self, power, modulo=None) -> Float:
        return Float(super(Float, self).__pow__(power, modulo))

    def __index__(self) -> int:
        return round(self)

    def floor(self) -> int:
        return math.ceil(self + constants.FLOAT_ADJUSTMENT)

    def ceil(self) -> int:
        return math.ceil(self - constants.FLOAT_ADJUSTMENT)

    def __str__(self) -> str:
        return super(Float, self).__str__()

    def __repr__(self):
        return f'Float({super(Float, self).__repr__()})'

    @staticmethod
    def sum(*args, **kwargs) -> Float:
        return Float(sum(*args, **kwargs))

    @staticmethod
    def max(*args, **kwargs) -> Float:
        if isinstance(args[0], Iterable) and len(args[0]) == 0:
            return O
        return Float(max(*args, **kwargs))

    @staticmethod
    def min(*args, **kwargs) -> Float:
        if isinstance(args[0], Iterable) and len(args[0]) == 0:
            return O
        return Float(min(*args, **kwargs))


Percent = Float
Ratio = Float
Date = int
Duration = int
Stock = int
Dollar = Float

O = Float(0)
ONE = Float(1)


def calculate_cagr(first_value: Float, last_value: Float, duration: Duration) -> Optional[Percent]:
    if first_value <= O:
        if last_value <= O:
            return O
        else:
            return ONE
    elif last_value <= O:
        return -ONE
    return (last_value / first_value) ** (constants.YEAR / duration) - ONE


def inverse_cagr(cagr: Percent, duration: Duration) -> Optional[Percent]:
    if cagr <= O:
        return -ONE
    return (1 + cagr) ** (duration / constants.YEAR) - 1


def min_max(
        value: Union[float, int, Float], min_value: Union[float, int, Float], max_value: Union[float, int, Float]) -> \
        Union[float, int, Float]:
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


class TqdmParallel(Parallel):
    def __init__(self, use_tqdm=True, total: int = None, desc: str = '', *args, **kwargs):
        self._use_tqdm = use_tqdm
        self._total = total
        self.desc = desc
        super().__init__(n_jobs=multiprocessing.cpu_count(), *args, **kwargs)

    def __call__(self, *args, **kwargs):
        with tqdm(disable=not self._use_tqdm, total=self._total, desc=self.desc) as self._pbar:
            return Parallel.__call__(self, *args, **kwargs)

    def print_progress(self):
        if self._total is None:
            self._pbar.total = self.n_dispatched_tasks
        self._pbar.n = self.n_completed_tasks
        self._pbar.refresh()
