import logging
import sys
from unittest import TestCase

from autologging import traced, logged, TRACE

from common import constants
from common.util import calculate_cagr, min_max, weighted_average


@traced
@logged
class TestUtil(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s'),
            level=TRACE if sys.gettrace() else logging.WARNING, stream=sys.stderr)

    def setUp(self) -> None:
        logging.info(f'****  setUp for {self._testMethodName} of {type(self).__name__}')

    def test_calculate_cagr(self):
        self.assertAlmostEqual(calculate_cagr(0, 2, constants.YEAR), 1)
        self.assertAlmostEqual(calculate_cagr(1, 0, constants.YEAR), -1)
        self.assertAlmostEqual(calculate_cagr(0, 0, constants.YEAR), 0)
        self.assertAlmostEqual(calculate_cagr(-1, 0, constants.YEAR), 0)
        self.assertAlmostEqual(calculate_cagr(0, -1, constants.YEAR), 0)
        self.assertAlmostEqual(calculate_cagr(-1, 1, constants.YEAR), 1)
        self.assertAlmostEqual(calculate_cagr(1, 2, constants.YEAR), 1)
        self.assertAlmostEqual(calculate_cagr(1, 2, constants.YEAR / 2), 3)

    def test_min_max(self):
        self.assertAlmostEqual(min_max(1, 2, 3), 2)
        self.assertAlmostEqual(min_max(4, 2, 3), 3)
        self.assertAlmostEqual(min_max(2.5, 2, 3), 2.5)

    def test_weighted_average(self):
        self.assertAlmostEqual(weighted_average([1, 1], [2, 2]), 1)
        self.assertAlmostEqual(weighted_average([1, 2], [2, 2]), 1.5)
        self.assertAlmostEqual(weighted_average([1, 2], [1, 2]), 5 / 3)
