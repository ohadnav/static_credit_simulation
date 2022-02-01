import logging
from typing import Callable, List, Optional, Tuple, Any

from joblib import delayed

from common.context import DataGenerator, SimulationContext
from common.local_numbers import Float
from common.util import TqdmParallel
from tests.util_test import BaseTestCase


def func(data_generator: DataGenerator, context: SimulationContext):
    return data_generator.max_purchase_order_size * context.loan_duration


class StatisticalTestCase(BaseTestCase):
    def setUp(self) -> None:
        super(StatisticalTestCase, self).setUp()
        self.data_generator.num_merchants = 100
        self.data_generator.num_products = 10


def statistical_test_mean_error(
        test_case: StatisticalTestCase, test_iteration: Callable, mean_error: float = 0.01, times: int = 100, *args,
        **kwargs):
    logging_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)
    desc = f'{test_case._testMethodName}'
    errors = TqdmParallel(desc=desc, total=times)(
        delayed(test_iteration)(test_case.data_generator, test_case.context, test_case.factory, *args, **kwargs) for _
            in range(times))
    actual_mean_error = Float.sum(errors) / times
    test_case.assertLess(actual_mean_error, mean_error)
    print(f'mean_error = {actual_mean_error}')
    logging.getLogger().setLevel(logging_level)


def statistical_test_bool(
        test_case: StatisticalTestCase, test_iteration: Callable,
        times: int = 20, min_frequency: Optional[float] = None, max_frequency: Optional[float] = None, *args, **kwargs):
    assert min_frequency is not None or max_frequency is not None
    logging_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger().setLevel(logging.WARNING)
    results = TqdmParallel(desc=f'{test_case._testMethodName}', total=times)(
        delayed(test_iteration)(test_case.data_generator, test_case.context, test_case.factory, *args, **kwargs) for _
            in range(times))
    is_true = translate_results(results)
    print_results(is_true)
    validate_results(test_case, min_frequency, max_frequency, is_true)
    logging.getLogger().setLevel(logging_level)


# noinspection PyUnusedLocal
def validate_results(
        test_case: StatisticalTestCase, min_frequency: Optional[float], max_frequency: Optional[float],
        is_true: List[List[Tuple[bool, Any]]]):
    for i in range(len(is_true)):
        count_bigger = len([a for a in is_true[i] if a[0]])
        true_ratio = count_bigger / len(is_true[i])
        false_cases = [a for a in is_true[i] if not a[0]]
        true_cases = [a for a in is_true[i] if a[0]]
        if min_frequency is not None:
            test_case.assertGreaterEqual(true_ratio, min_frequency, f'list {i}')
        if max_frequency is not None:
            test_case.assertLessEqual(true_ratio, max_frequency, f'list {i}')


def print_results(is_true: List[List[Tuple[bool, Any]]]):
    for i in range(len(is_true)):
        count_bigger = len([a for a in is_true[i] if a[0]])
        true_ratio = count_bigger / len(is_true[i])
        list_name = str(i)
        if type(is_true[i][0][1]) is tuple:
            if type(is_true[i][0][1][0]) is str:
                list_name = is_true[i][0][1][0]
        print(f'list {list_name} ratio is {true_ratio}')


def translate_results(results: List[List]) -> List[List[Tuple[bool, Any]]]:
    is_true = [[] for _ in range(len(results[0]))]
    for t in results:
        for i in range(len(is_true)):
            is_true[i].append(t[i])
    return is_true
