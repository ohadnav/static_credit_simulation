from __future__ import annotations

import multiprocessing
from random import random

from joblib import Parallel
from tqdm.auto import tqdm

from local_numbers import Float


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
