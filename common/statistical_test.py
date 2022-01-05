import logging
from typing import Callable
from unittest import TestCase

from autologging import TRACE


def statistical_test(max_error: float = 0.1, mean_error: float = 0.01, times: int = 100):
    def decorator(test_case: Callable):
        def wrapper(test_instance: TestCase):
            logging.getLogger().setLevel(logging.CRITICAL)
            errors = []
            for _ in range(times):
                test_case(test_instance, errors)
                test_instance.assertLess(errors[-1], max_error)
            test_instance.assertLess(sum(errors) / times, mean_error)
            logging.getLogger().setLevel(TRACE)

        return wrapper

    return decorator
