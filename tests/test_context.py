from unittest import mock
from unittest.mock import MagicMock

from common import constants
from tests.util_test import BaseTestCase


class TestDataGenerator(BaseTestCase):
    def test_remove_randomness(self):
        self.data_generator.remove_randomness()
        self.assertEqual(self.data_generator.random(), constants.NO_VOLATILITY)
        self.assertEqual(self.data_generator.normal_ratio(), constants.NO_VOLATILITY)

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
