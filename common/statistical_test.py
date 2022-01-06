import logging
from typing import Callable, List, Union, Optional
from unittest import TestCase

from autologging import TRACE
from tqdm import tqdm

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


def statistical_test_bigger(times: int = 100, confidence: Percent = 0.95, num_lists: int = 1):
    def decorator(test_case: Callable):
        def wrapper(test_instance: TestCase):
            logging.getLogger().setLevel(logging.CRITICAL)
            is_bigger: Union[List[bool], List[List[bool]]] = [] if num_lists == 1 else [[] for _ in range(num_lists)]
            for _ in tqdm(range(times), desc=f'{test_instance._testMethodName}: '):
                test_case(test_instance, is_bigger)
            if num_lists == 1:
                validate_bigger(is_bigger, test_instance)
            else:
                for i in range(len(is_bigger)):
                    validate_bigger(is_bigger[i], test_instance, f'is_bigger list {i}')

        def validate_bigger(is_bigger, test_instance, label: Optional[str] = None):
            count_bigger = len([a for a in is_bigger if a])
            test_instance.assertGreaterEqual(count_bigger / times, confidence, label)
            logging.getLogger().setLevel(TRACE)

        return wrapper

    return decorator
