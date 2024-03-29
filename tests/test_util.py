from random import uniform

from common import constants
from common.local_numbers import Float, O, ONE, TWO, Int, Duration
from common.util import calculate_cagr, min_max, weighted_average, inverse_cagr
from tests.util_test import BaseTestCase


class TestUtil(BaseTestCase):
    def test_calculate_cagr(self):
        self.assertEqual(calculate_cagr(O, TWO, constants.YEAR), ONE)
        self.assertEqual(calculate_cagr(ONE, O, constants.YEAR), -ONE)
        self.assertEqual(calculate_cagr(O, O, constants.YEAR), O)
        self.assertEqual(calculate_cagr(-ONE, O, constants.YEAR), O)
        self.assertEqual(calculate_cagr(O, -ONE, constants.YEAR), O)
        self.assertEqual(calculate_cagr(-ONE, ONE, constants.YEAR), ONE)
        self.assertEqual(calculate_cagr(ONE, TWO, constants.YEAR), ONE)
        self.assertEqual(calculate_cagr(ONE, TWO, constants.YEAR / TWO), 3)

    def test_min_max(self):
        self.assertEqual(min_max(1, 2, 3), 2)
        self.assertEqual(min_max(4, 2, 3), 3)
        self.assertEqual(min_max(2.5, 2, 3), 2.5)
        self.assertTrue(type(min_max(Int(3), 2, 3)), Int)
        self.assertTrue(type(min_max(Float(3), 2, 3)), Float)
        self.assertTrue(type(min_max(Duration(3), 2, 3)), Duration)

    def test_weighted_average(self):
        self.assertEqual(weighted_average([1, 1], [2, 2]), 1)
        self.assertEqual(weighted_average([1, 2], [2, 2]), 1.5)
        self.assertEqual(weighted_average([1, 2], [1, 2]), 5 / 3)

    def test_inverse_cagr(self):
        cagr = Float(uniform(0.1, 100))
        self.assertEqual(inverse_cagr(cagr, constants.YEAR), cagr)
        self.assertEqual(inverse_cagr(cagr, constants.YEAR / 2), (1 + cagr) ** 0.5 - 1)
        self.assertEqual(inverse_cagr(O, constants.YEAR), -ONE)
        self.assertEqual(inverse_cagr(-ONE, constants.YEAR), -ONE)

