import logging
from typing import Callable, List, Union, Optional, Tuple, Any
from unittest import TestCase

from autologging import TRACE
from tqdm import tqdm

from common.util import Percent


def statistical_test_mean_error(max_error: float = 0.1, mean_error: float = 0.01, times: int = 100):
    def decorator(test_case: Callable):
        def wrapper(test_instance: TestCase):
            logging.getLogger().setLevel(logging.CRITICAL)
            errors = []
            for i in range(times):
                test_case(test_instance, errors)
                test_instance.assertLess(errors[-1], max_error)
                assert len(errors) == i + 1
            test_instance.assertLess(sum(errors) / times, mean_error)
            logging.getLogger().setLevel(TRACE)

        return wrapper

    return decorator


def statistical_test_bool(times: int = 100, confidence: Percent = 0.8, num_lists: int = 1):
    def decorator(test_case: Callable):
        def wrapper(test_instance: TestCase):
            logging.getLogger().setLevel(logging.CRITICAL)
            is_true: List[List[Union[bool, Tuple[bool, Any]]]] = [[] for _ in range(num_lists)]
            for i in tqdm(range(times), desc=f'{test_instance._testMethodName}: '):
                test_case(test_instance, is_true)
                for j in range(num_lists):
                    assert len(is_true[j]) == i + 1, f'{i + 1} != len( {len(is_true[j])})'
            for i in range(len(is_true)):
                validate_bigger(is_true[i], test_instance, f'is_true list {i}')
            logging.getLogger().setLevel(TRACE)

        def is_iteration_true(value: Union[bool, Tuple[bool, Any]]) -> bool:
            if isinstance(value, bool):
                return value
            return value[0]

        # noinspection PyUnusedLocal
        def validate_bigger(is_true: List[bool], test_instance: TestCase, msg: Optional[str] = None):
            count_bigger = len([a for a in is_true if is_iteration_true(a)])
            true_ratio = count_bigger / times
            false_cases = [a for a in is_true if not is_iteration_true(a)]
            true_cases = [a for a in is_true if is_iteration_true(a)]
            test_instance.assertGreaterEqual(true_ratio, confidence, msg)

        return wrapper

    return decorator
