from unittest import TestCase

from common import constants
from common.numbers import Float, TWO, human_format, ONE, Int, human_format_duration, Duration
from tests.util_test import BaseTestCase


class TestFloat(BaseTestCase):
    def setUp(self) -> None:
        super(TestFloat, self).setUp()
        self._float = TWO

    def test_comparison(self):
        # eq
        self.assertFalse(ONE == TWO)
        self.assertFalse(TWO == ONE)
        self.assertTrue(ONE == ONE)
        self.assertTrue(ONE == Float(1.000000001))
        self.assertTrue(Float(0.99999999999) == ONE)
        # lt
        self.assertTrue(ONE < TWO)
        self.assertFalse(ONE < ONE)
        self.assertFalse(ONE < Float(1.000000001))
        self.assertFalse(Float(0.99999999999) < ONE)
        # le
        self.assertTrue(ONE <= ONE)
        self.assertTrue(ONE <= Float(1.000000001))
        # gt
        self.assertTrue(TWO > ONE)
        self.assertTrue(Float(10 ** 8 + 1) > Float(10 ** 8))
        self.assertFalse(ONE > ONE)
        self.assertFalse(Float(1.000000001) > ONE)
        self.assertFalse(ONE > Float(0.99999999999))
        # ge
        self.assertTrue(ONE >= ONE)
        self.assertTrue(Float(1.000000001) >= ONE)

    def test_arithmetic(self):
        self.assertEqual(self._float + 1, 3)
        self.assertEqual(self._float - 1, 1)
        self.assertEqual(self._float * 2, 4)
        self.assertEqual(self._float / 2, 1)
        self.assertEqual(self._float ** 2, 4)

    def test_help_func(self):
        self.assertEqual(Float.min(1, 2), Float(1))
        self.assertEqual(Float.min([]), Float(0))
        self.assertEqual(Float.sum([1, 2]), Float(3))

    def test_typing(self):
        self.assertTrue(type(self._float + 1), Float)
        self.assertTrue(type(self._float - 1), Float)
        self.assertTrue(type(self._float * 1), Float)
        self.assertTrue(type(self._float / 1), Float)
        self.assertTrue(type(self._float ** 1), Float)
        self.assertTrue(type(Float.min(1, 2)), Float)
        self.assertTrue(type(Float.min([])), Float)
        self.assertTrue(type(Float.sum([1, 2])), Float)

    def test_average(self):
        self.assertEqual(Float.average([1, 2, 3]), Float(2))

    def test_is_close(self):
        self.assertTrue(Float(0).is_close(0 + constants.FLOAT_CLOSE_TOLERANCE))
        self.assertTrue(Float(1).is_close(1 + constants.FLOAT_CLOSE_TOLERANCE))
        self.assertTrue(Float(1).is_close(1 - constants.FLOAT_CLOSE_TOLERANCE + 0.001))
        self.assertTrue(Float(10).is_close(10 + constants.FLOAT_CLOSE_TOLERANCE * 10))
        self.assertTrue(Float(-10).is_close(-10 + constants.FLOAT_CLOSE_TOLERANCE * 10))
        self.assertFalse(Float(10).is_close(10 + constants.FLOAT_CLOSE_TOLERANCE * 11))
        self.assertFalse(Float(0).is_close(0 + constants.FLOAT_CLOSE_TOLERANCE + 0.01))

    def test_from_human_format(self):
        self.assertEqual(Float.from_human_format('1M'), 10 ** 6)
        self.assertEqual(Float.from_human_format('1000T'), 10 ** 15)
        self.assertEqual(Float.from_human_format('19.9K'), 19900)
        self.assertEqual(Float.from_human_format('0.5'), 0.5)
        self.assertEqual(Float.from_human_format('0'), 0)


class TestNumbers(BaseTestCase):
    def test_human_format(self):
        self.assertEqual(human_format(999999), '1M')
        self.assertEqual(human_format(10 ** 15), '1000T')
        self.assertEqual(human_format(999499), '999K')
        self.assertEqual(human_format(6543165413), '6.5B')
        self.assertEqual(human_format(19900), '19.9K')
        self.assertEqual(human_format(9900), '9.9K')
        self.assertEqual(human_format(1), '1')
        self.assertEqual(human_format(0.5), '0.5')
        self.assertEqual(human_format(1.51), '1.51')
        self.assertEqual(human_format(0.0099), '0.01')
        self.assertEqual(human_format(0.00099), '0')

    def test_human_format_duration(self):
        self.assertEqual(human_format_duration(-10), '-(1wk 3d)')
        self.assertEqual(human_format_duration(0), '0d')
        self.assertEqual(human_format_duration(1), '1d')
        self.assertEqual(human_format_duration(6), '6d')
        self.assertEqual(human_format_duration(7), '1wk')
        self.assertEqual(human_format_duration(14), '2wk')
        self.assertEqual(human_format_duration(13), '1wk 6d')
        self.assertEqual(human_format_duration(30), '1mon')
        self.assertEqual(human_format_duration(31), '1mon 1d')
        self.assertEqual(human_format_duration(365), '1yr')
        self.assertEqual(human_format_duration(3650), '10yr')


class TestInt(BaseTestCase):
    def setUp(self) -> None:
        super(TestInt, self).setUp()
        self._int = Int(2)

    def test_arithmetic(self):
        self.assertEqual(self._int + 1, 3)
        self.assertEqual(self._int - 1, 1)
        self.assertEqual(self._int * 2, 4)
        self.assertEqual(self._int / 2, 1)
        self.assertEqual(self._int ** 2, 4)

    def test_typing(self):
        self.assertTrue(type(self._int + 1), Int)
        self.assertTrue(type(self._int + Float(1)), Int)
        self.assertTrue(type(self._int + Float(1.5)), Float)
        self.assertTrue(type(self._int - 1), Int)
        self.assertTrue(type(self._int - Float(1.5)), Float)
        self.assertTrue(type(self._int * 1), Int)
        self.assertTrue(type(self._int * 1.1), Float)
        self.assertTrue(type(self._int / 1), Int)
        self.assertTrue(type(self._int / 1.1), Float)
        self.assertTrue(type(self._int ** 1), Int)
        self.assertTrue(type(self._int ** Float(1)), Int)
        self.assertTrue(type(self._int ** 1.1), Float)

    def test_str(self):
        self.assertEqual(Int(1000).__str__(), '1K')


class TestDuration(TestCase):
    def setUp(self) -> None:
        super(TestDuration, self).setUp()
        self.duration = Duration(2)

    def test_typing(self):
        self.assertTrue(type(self.duration + 1), Duration)
        self.assertTrue(type(self.duration + Int(1)), Duration)
        self.assertTrue(type(self.duration + Float(1)), Duration)
        self.assertTrue(type(self.duration - 1), Duration)
        self.assertTrue(type(self.duration * 1), Duration)
        self.assertTrue(type(self.duration / 1), Duration)
        self.assertTrue(type(self.duration / 1.1), Float)
        self.assertTrue(type(self.duration ** 1), Duration)

    def test_str(self):
        self.assertEqual(Duration(1).__str__(), '1d')
