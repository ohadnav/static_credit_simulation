import math
import multiprocessing
from typing import Union, List, Optional

from joblib import Parallel
from tqdm.auto import tqdm

from common import constants

Percent = float
Ratio = float
Date = int
Duration = int
Stock = int
Dollar = float


def calculate_cagr(first_value: float, last_value: float, duration: Duration) -> Optional[Percent]:
    if first_value <= 0:
        if last_value <= 0:
            return 0
        else:
            return 1
    elif last_value <= 0:
        return -1
    return math.pow(last_value / first_value, constants.YEAR / duration) - 1


def inverse_cagr(cagr: Percent, duration: Duration) -> Optional[Percent]:
    if cagr <= 0:
        return -1
    return math.pow(1 + cagr, duration / constants.YEAR) - 1


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
