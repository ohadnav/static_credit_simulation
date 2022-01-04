import logging
import sys
from unittest import TestCase, mock
from unittest.mock import MagicMock

from autologging import TRACE

from common import constants
from common.context import DataGenerator


class TestDataGenerator(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=TRACE, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')
        self.data_generator = DataGenerator()

    def test_remove_randomness(self):
        self.data_generator.remove_randomness()
        self.assertEqual(self.data_generator.random(), constants.NO_VOLATILITY)
        self.assertEqual(self.data_generator.normal_ratio(), constants.NO_VOLATILITY)
        self.assertEqual(self.data_generator.normal(), 0)
        self.assertEqual(self.data_generator.randint(1, 1000), 1)

    @mock.patch('numpy.random.mtrand.normal')
    def test_normal(self, normal_mock: MagicMock):
        normal_mock.return_value = -10
        self.assertEqual(self.data_generator.normal(min_value=-2), -2)
        normal_mock.return_value = -10
        self.assertEqual(self.data_generator.normal(std=1.5), -1.5 * constants.MAX_RANDOM_DEVIATION)
        normal_mock.return_value = 10
        self.assertEqual(self.data_generator.normal(max_value=3), 3)
        self.assertEqual(self.data_generator.normal(std=2), 2 * constants.MAX_RANDOM_DEVIATION)
        normal_mock.return_value = 0.5
        self.assertEqual(self.data_generator.normal(), 0.5)

    @mock.patch('numpy.random.mtrand.normal')
    @mock.patch('numpy.random.mtrand.random')
    def test_normal_ratio(self, random_mock: MagicMock, normal_mock: MagicMock):
        normal_mock.return_value = 1
        random_mock.return_value = 0.89
        self.assertEqual(self.data_generator.normal_ratio(chance_positive=0.9), 2)
        normal_mock.return_value = -1
        self.assertEqual(self.data_generator.normal_ratio(chance_positive=0.9), 2)
        normal_mock.return_value = 1
        random_mock.return_value = 0.11
        self.assertEqual(self.data_generator.normal_ratio(chance_positive=0.1), 0.5)
        normal_mock.return_value = 10
        random_mock.return_value = 0.09
        self.assertEqual(self.data_generator.normal_ratio(std=2, max_ratio=2), 5)