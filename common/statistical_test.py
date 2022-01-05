import logging
from typing import Callable

from autologging import TRACE


def statistical_test(test: Callable, max_error: float = 0.1, mean_error: float = 0.01, times: int = 100):
    def test_wrapper(*args, **kwargs):
        logging.getLogger().setLevel(logging.CRITICAL)
        errors = []
        test_instance = args[0]
        for _ in range(times):
            test(test_instance, errors)
            test_instance.assertLess(errors[-1], max_error)
        test_instance.assertLess(sum(errors) / times, mean_error)
        logging.getLogger().setLevel(TRACE)

    return test_wrapper
