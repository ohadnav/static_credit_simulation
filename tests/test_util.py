from random import uniform
from time import time, sleep

from joblib import delayed

from common import constants
from common.util import calculate_cagr, min_max, weighted_average, inverse_cagr, TqdmParallel, Float, ONE, O
from tests.util_test import BaseTestCase


class TestUtil(BaseTestCase):
    def test_calculate_cagr(self):
        two = Float(2)
        self.assertAlmostEqual(calculate_cagr(O, two, constants.YEAR), ONE)
        self.assertAlmostEqual(calculate_cagr(ONE, O, constants.YEAR), -ONE)
        self.assertAlmostEqual(calculate_cagr(O, O, constants.YEAR), O)
        self.assertAlmostEqual(calculate_cagr(-ONE, O, constants.YEAR), O)
        self.assertAlmostEqual(calculate_cagr(O, -ONE, constants.YEAR), O)
        self.assertAlmostEqual(calculate_cagr(-ONE, ONE, constants.YEAR), ONE)
        self.assertAlmostEqual(calculate_cagr(ONE, two, constants.YEAR), ONE)
        self.assertAlmostEqual(calculate_cagr(ONE, two, constants.YEAR / two), 3)

    def test_min_max(self):
        self.assertAlmostEqual(min_max(1, 2, 3), 2)
        self.assertAlmostEqual(min_max(4, 2, 3), 3)
        self.assertAlmostEqual(min_max(2.5, 2, 3), 2.5)

    def test_weighted_average(self):
        self.assertAlmostEqual(weighted_average([1, 1], [2, 2]), 1)
        self.assertAlmostEqual(weighted_average([1, 2], [2, 2]), 1.5)
        self.assertAlmostEqual(weighted_average([1, 2], [1, 2]), 5 / 3)

    def test_inverse_cagr(self):
        cagr = Float(uniform(0.1, 100))
        self.assertAlmostEqual(inverse_cagr(cagr, constants.YEAR), cagr)
        self.assertAlmostEqual(inverse_cagr(cagr, constants.YEAR / 2), (1 + cagr) ** 0.5 - 1)
        self.assertAlmostEqual(inverse_cagr(O, constants.YEAR), -ONE)
        self.assertAlmostEqual(inverse_cagr(-ONE, constants.YEAR), -ONE)

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
        self.assertDeepAlmostEqual(result, [0, 1, 2, 3, 4])


class TestFloat(BaseTestCase):
    def setUp(self) -> None:
        super(TestFloat, self).setUp()
        self.float = Float(1)

    def test_comparison(self):
        # eq
        self.assertFalse(Float(1) == Float(2))
        self.assertFalse(Float(2) == Float(1))
        self.assertTrue(Float(1) == Float(1))
        self.assertTrue(Float(1) == Float(1.000000001))
        self.assertTrue(Float(0.99999999999) == Float(1))
        # lt
        self.assertTrue(Float(1) < Float(2))
        self.assertFalse(Float(1) < Float(1))
        self.assertFalse(Float(1) < Float(1.000000001))
        self.assertFalse(Float(0.99999999999) < Float(1))
        # le
        self.assertTrue(Float(1) <= Float(1))
        self.assertTrue(Float(1) <= Float(1.000000001))
        # gt
        self.assertTrue(Float(2) > Float(1))
        self.assertFalse(Float(1) > Float(1))
        self.assertFalse(Float(1.000000001) > Float(1))
        self.assertFalse(Float(1) > Float(0.99999999999))
        # ge
        self.assertTrue(Float(1) >= Float(1))
        self.assertTrue(Float(1.000000001) >= Float(1))

    def test_arithmetic(self):
        self.assertEqual(self.float + 1, 2)
        self.assertEqual(self.float - 1, 0)
        self.assertEqual(self.float * 2, 2)
        self.assertEqual(self.float / 2, 0.5)
