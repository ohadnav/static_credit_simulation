import logging
from typing import Callable, List, Optional, Tuple, Any

from joblib import delayed

from common.util import Percent, TqdmParallel
from tests.util_test import StatisticalTestCase


def statistical_test_mean_error(
        test_case: StatisticalTestCase, test_iteration: Callable, mean_error: float = 0.01, times: int = 100):
    logging_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)
    desc = f'{test_case._testMethodName}'
    errors = TqdmParallel(desc=desc, total=times)(
        delayed(test_iteration)(test_case.data_generator, test_case.context) for _ in range(times))
    test_case.assertLess(sum(errors) / times, mean_error)
    logging.getLogger().setLevel(logging_level)


def statistical_test_bool(
        test_case: StatisticalTestCase, test_iteration: Callable,
        times: int = 100, min_frequency: Optional[Percent] = None, max_frequency: Optional[Percent] = None):
    assert min_frequency is not None or max_frequency is not None
    logging_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)
    results = TqdmParallel(desc=f'{test_case._testMethodName}', total=times)(
        delayed(test_iteration)(test_case.data_generator, test_case.context, test_case.factory) for _ in range(times))
    is_true = translate_results(results)
    print_results(is_true)
    validate_results(test_case, min_frequency, max_frequency, is_true)
    logging.getLogger().setLevel(logging_level)


def validate_results(
        test_case: StatisticalTestCase, min_frequency: Optional[Percent], max_frequency: Optional[Percent],
        is_true: List[List[Tuple[bool, Any]]]):
    for i in range(len(is_true)):
        count_bigger = len([a for a in is_true[i] if a[0]])
        true_ratio = count_bigger / len(is_true[i])
        if min_frequency is not None:
            test_case.assertGreaterEqual(true_ratio, min_frequency, f'list {i}')
        if max_frequency is not None:
            test_case.assertLessEqual(true_ratio, max_frequency, f'list {i}')


def print_results(is_true: List[List[Tuple[bool, Any]]]):
    for i in range(len(is_true)):
        count_bigger = len([a for a in is_true[i] if a[0]])
        true_ratio = count_bigger / len(is_true[i])
        print(f'list {i} ratio is {true_ratio}')


def translate_results(results: List[List]) -> List[List[Tuple[bool, Any]]]:
    is_true = [[] for _ in range(len(results[0]))]
    for t in results:
        for i in range(len(is_true)):
            is_true[i].append(t[i])
    return is_true
