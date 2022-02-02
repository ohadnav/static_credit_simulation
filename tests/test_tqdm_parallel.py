from time import sleep, time

from joblib import delayed

from common.tqdm_parallel import TqdmParallel
from util_test import BaseTestCase


class TestTqdmParallel(BaseTestCase):
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
