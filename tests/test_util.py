import math
from random import uniform
from time import time, sleep

from joblib import delayed

from common import constants
from common.util import calculate_cagr, min_max, weighted_average, inverse_cagr, TqdmParallel
from tests.util_test import BaseTestCase


class TestUtil(BaseTestCase):
    def test_calculate_cagr(self):
        self.assertAlmostEqual(calculate_cagr(0, 2, constants.YEAR), 1)
        self.assertAlmostEqual(calculate_cagr(1, 0, constants.YEAR), -1)
        self.assertAlmostEqual(calculate_cagr(0, 0, constants.YEAR), 0)
        self.assertAlmostEqual(calculate_cagr(-1, 0, constants.YEAR), 0)
        self.assertAlmostEqual(calculate_cagr(0, -1, constants.YEAR), 0)
        self.assertAlmostEqual(calculate_cagr(-1, 1, constants.YEAR), 1)
        self.assertAlmostEqual(calculate_cagr(1, 2, constants.YEAR), 1)
        self.assertAlmostEqual(calculate_cagr(1, 2, constants.YEAR / 2), 3)

    def test_min_max(self):
        self.assertAlmostEqual(min_max(1, 2, 3), 2)
        self.assertAlmostEqual(min_max(4, 2, 3), 3)
        self.assertAlmostEqual(min_max(2.5, 2, 3), 2.5)

    def test_weighted_average(self):
        self.assertAlmostEqual(weighted_average([1, 1], [2, 2]), 1)
        self.assertAlmostEqual(weighted_average([1, 2], [2, 2]), 1.5)
        self.assertAlmostEqual(weighted_average([1, 2], [1, 2]), 5 / 3)

    def test_inverse_cagr(self):
        cagr = uniform(0.1, 100)
        self.assertAlmostEqual(inverse_cagr(cagr, constants.YEAR), cagr)
        self.assertAlmostEqual(inverse_cagr(cagr, constants.YEAR / 2), math.pow(1 + cagr, 0.5) - 1)
        self.assertAlmostEqual(inverse_cagr(0, constants.YEAR), -1)
        self.assertAlmostEqual(inverse_cagr(-1, constants.YEAR), -1)

    def test_parallel(self):
        def sleep_func(i):
            sleep(0.2)
            return i

        times = 5
        start_time = time()
        [sleep_func(i) for i in range(times)]
        unparallel_time = time() - start_time
        start_time2 = time()
        result = TqdmParallel(use_tqdm=False)(delayed(sleep_func)(i) for i in range(times))
        parallel_time = time() - start_time2
        self.assertLess(parallel_time, unparallel_time)
        self.assertListEqual(result, [0, 1, 2, 3, 4])
