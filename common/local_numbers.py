from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Union, List, Optional

from common import constants


class Float(float):
    def __eq__(self, other):
        if other is None:
            return False
        if math.isclose(self, other, abs_tol=constants.FLOAT_EQUALITY_TOLERANCE):
            return True
        return super(Float, self).__eq__(other)

    def __hash__(self):
        return super(Float, self).__hash__()

    def __lt__(self, other) -> bool:
        if self == other:
            return False
        return super(Float, self).__lt__(other)

    def __le__(self, other) -> bool:
        if self == other:
            return True
        return super(Float, self).__le__(other)

    def __gt__(self, other) -> bool:
        if self == other:
            return False
        return super(Float, self).__gt__(other)

    def __ge__(self, other) -> bool:
        if self == other:
            return True
        return super(Float, self).__ge__(other)

    def __add__(self, other) -> Float:
        return Float(super(Float, self).__add__(other))

    def __mul__(self, other) -> Float:
        return Float(super(Float, self).__mul__(other))

    def __sub__(self, other) -> Float:
        return Float(super(Float, self).__sub__(other))

    def __truediv__(self, other) -> Float:
        return Float(super(Float, self).__truediv__(other))

    def __pow__(self, power, modulo=None) -> Float:
        return Float(super(Float, self).__pow__(power, modulo))

    def __index__(self) -> int:
        return int(self)

    def is_close(self, other: Union[float, int], rel: float = constants.FLOAT_CLOSE_TOLERANCE):
        return math.isclose(self, other, rel_tol=rel, abs_tol=rel)

    def floor(self) -> int:
        return math.ceil(self + constants.FLOAT_EQUALITY_TOLERANCE)

    def ceil(self) -> int:
        return math.ceil(self - constants.FLOAT_EQUALITY_TOLERANCE)

    def __str__(self) -> str:
        return human_format(self)

    def __repr__(self):
        return f'Float({human_format(self)})'

    @staticmethod
    def is_float(s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False

    @classmethod
    def from_human_format(cls, human_format: str) -> Float:
        if Float.is_float(human_format):
            return Float(float(human_format))
        return Float(float(human_format[:-1])) * 10 ** (3 * HUMAN_FORMAT_POSTFIX.index(human_format[-1]))

    @staticmethod
    def sum(*args, **kwargs) -> Float:
        return Float(sum(*args, **kwargs))

    @staticmethod
    def max(*args, **kwargs) -> Float:
        if isinstance(args[0], Iterable) and len(args[0]) == 0:
            return O
        return Float(max(*args, **kwargs))

    @staticmethod
    def min(*args, **kwargs) -> Float:
        if isinstance(args[0], Iterable) and len(args[0]) == 0:
            return O
        return Float(min(*args, **kwargs))

    @staticmethod
    def mean(values: List[float]) -> Float:
        if len(values) == 0:
            return O
        return Float.sum(values) / len(values)


class Int(int):
    def __add__(self, other) -> Union[Int, Float]:
        if Int.is_true_float(other):
            return Float(self) + other
        return Int(super(Int, self).__add__(round(other)))

    def __mul__(self, other) -> Union[Int, Float]:
        if Int.is_true_float(other):
            return Float(self) * other
        return Int(super(Int, self).__mul__(round(other)))

    def __sub__(self, other) -> Union[Int, Float]:
        if Int.is_true_float(other):
            return Float(self) - other
        return Int(super(Int, self).__sub__(round(other)))

    def __truediv__(self, other) -> Union[Float, Int]:
        result = Float(self) / other
        if Int.is_true_float(result):
            return result
        else:
            return Int(result)

    def __pow__(self, power, modulo=None) -> Union[Int, Float]:
        if Int.is_true_float(power):
            return Float(self).__pow__(power, modulo)
        return Int(super(Int, self).__pow__(round(power), modulo))

    def __index__(self):
        return int(self)

    def __str__(self) -> str:
        return human_format(self)

    def __repr__(self):
        return f'Int({human_format(self)})'

    @staticmethod
    def is_true_float(other):
        return isinstance(other, float) and other != round(other)

    @staticmethod
    def sum(*args, **kwargs) -> Int:
        return Int(sum(*args, **kwargs))

    @staticmethod
    def max(*args, **kwargs) -> Int:
        if isinstance(args[0], Iterable) and len(args[0]) == 0:
            return O_INT
        return Int(max(*args, **kwargs))

    @staticmethod
    def min(*args, **kwargs) -> Int:
        if isinstance(args[0], Iterable) and len(args[0]) == 0:
            return O_INT
        return Int(min(*args, **kwargs))


class Duration(Int):
    def __add__(self, other) -> Union[Duration, Float]:
        if Int.is_true_float(other):
            return Float(self) + other
        return Duration(super(Duration, self).__add__(other))

    def __mul__(self, other) -> Union[Duration, Float]:
        if Int.is_true_float(other):
            return Float(self) * other
        return Duration(super(Duration, self).__mul__(other))

    def __sub__(self, other) -> Union[Duration, Float]:
        if Int.is_true_float(other):
            return Float(self) - other
        return Duration(super(Duration, self).__sub__(other))

    def __truediv__(self, other) -> Union[Float, Duration]:
        result = super(Duration, self).__truediv__(other)
        if type(result) == Int:
            return Duration(result)
        return result

    def __pow__(self, power, modulo=None) -> Union[Duration, Float]:
        if Int.is_true_float(power):
            return Float(self).__pow__(power, modulo)
        return Duration(super(Duration, self).__pow__(power, modulo))

    def __index__(self):
        return int(self)

    def __str__(self) -> str:
        return human_format_duration(self)

    def __repr__(self):
        return f'Duration({human_format_duration(self)})'

    def from_date(self, date: Date) -> Duration:
        return self - date + 1

    @staticmethod
    def sum(*args, **kwargs) -> Duration:
        return Duration(Int.sum(*args, **kwargs))

    @staticmethod
    def max(*args, **kwargs) -> Duration:
        return Duration(Int.max(*args, **kwargs))

    @staticmethod
    def min(*args, **kwargs) -> Duration:
        return Duration(Int.min(*args, **kwargs))


def human_format_duration(days: int) -> str:
    if days < 0:
        return f'-({human_format_duration(-days)})'
    if days == 0:
        return '0d'
    sizes = [1, constants.WEEK, constants.MONTH, constants.YEAR]
    postfix = ['d', 'wk', 'mon', 'yr']
    numbers = {}
    remainder = days
    for i in reversed(range(len(sizes))):
        if remainder >= sizes[i]:
            numbers[postfix[i]] = remainder // sizes[i]
            remainder -= numbers[postfix[i]] * sizes[i]
    return ' '.join([f'{n}{p}' for p, n in numbers.items()])


HUMAN_FORMAT_POSTFIX = ['', 'K', 'M', 'B', 'T']


def human_format(num: Union[float, int]) -> str:
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000 and magnitude < len(HUMAN_FORMAT_POSTFIX) - 1:
        magnitude += 1
        num /= 1000.0
    deci = calculate_decimal_figures(num)
    return '{}{}'.format('{:.{deci}f}'.format(num, deci=deci).rstrip('0').rstrip('.'), HUMAN_FORMAT_POSTFIX[magnitude])


def calculate_decimal_figures(num: Union[float, int]) -> int:
    abs_num = abs(num)
    if abs_num >= 2 or O == abs_num:
        return 1
    if abs_num >= 0.1:
        return 2
    return -math.floor(math.log10(abs_num)) + 1


Percent = Float
Ratio = Float
Date = Duration
Stock = Int
Dollar = Float
O = Float(0)
O_INT = Int(0)
ONE = Float(1)
HALF = Float(0.5)
TWO = Float(2)
ONE_INT = Duration(1)
TWO_INT = Duration(2)


@dataclass(unsafe_hash=True)
class FloatRange:
    min_value: Optional[Float] = None
    max_value: Optional[Float] = None

    def __str__(self):
        return f'[{self.min_value if self.min_value is not None else "-inf"}, ' \
               f'{self.max_value if self.max_value is not None else "inf"})'

    def __repr__(self):
        return self.__str__()

    def update(self, value: Float):
        if self.min_value is None:
            self.min_value = value
        if self.max_value is None:
            self.max_value = value
        self.min_value = Float.min(self.min_value, value)
        self.max_value = Float.max(self.max_value, value)
