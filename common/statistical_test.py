import logging
from typing import Callable, List
from unittest import TestCase

from autologging import TRACE

from common.util import Percent


def statistical_test_mean_error(max_error: float = 0.1, mean_error: float = 0.01, times: int = 100):
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


def statistical_test_bigger(times: int = 100, confidence: Percent = 0.95):
    def decorator(test_case: Callable):
        def wrapper(test_instance: TestCase):
            logging.getLogger().setLevel(logging.CRITICAL)
            is_bigger: List[bool] = []
            for _ in range(times):
                test_case(test_instance, is_bigger)
            count_bigger = len([a for a in is_bigger if a])
            test_instance.assertGreaterEqual(count_bigger / times, confidence)
            logging.getLogger().setLevel(TRACE)

        return wrapper

    return decorator
