from __future__ import annotations

import multiprocessing
from random import random
from typing import Union, List, Optional, TypeVar, Mapping

from joblib import Parallel
from tqdm.auto import tqdm

from common import constants
from common.numbers import Float, Percent, Duration, O, ONE, Int

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


class LiveRate:
    def __init__(self):
        self.id = random()
        self.name = ''
        self.reset()

    def reset(self):
        self.positive = 0
        self.total = 0

    def __hash__(self):
        return self.id

    def __str__(self):
        # return f'{self.name}: {round(self.positive / self.total if self.total > 0 else 0, 2)}'
        return f'{self.name}: {Float(100 * self.positive / self.total if self.total > 0 else 0)}%'


global LIVE_RATE
# noinspection PyRedeclaration
LIVE_RATE = LiveRate()


class TqdmParallel(Parallel):
    def __init__(self, use_tqdm=True, total: int = None, desc: str = '', show_live_rate: bool = False, *args, **kwargs):
        self._use_tqdm = use_tqdm
        self._total = total
        self.desc = desc
        self.show_live_rate = show_live_rate
        if show_live_rate:
            super().__init__(n_jobs=multiprocessing.cpu_count(), require='sharedmem', *args, **kwargs)
        else:
            super().__init__(n_jobs=multiprocessing.cpu_count(), *args, **kwargs)

    def __call__(self, *args, **kwargs):
        with tqdm(disable=not self._use_tqdm, total=self._total, desc=self.desc) as self._pbar:
            return Parallel.__call__(self, *args, **kwargs)

    def print_progress(self):
        if self._total is None:
            self._pbar.total = self.n_dispatched_tasks
        self._pbar.n = self.n_completed_tasks
        if self.show_live_rate:
            self._pbar.set_postfix_str(str(LIVE_RATE))
        self._pbar.refresh()


def shout_print(msg: str):
    print(f'\n\n{"*" * len(msg)}\n')
    print(msg)
    print(f'\n{"*" * len(msg)}')


def flatten(_list: List):
    return [item for sublist in _list for item in sublist]
