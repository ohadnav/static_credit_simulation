from __future__ import annotations

import math
from typing import Iterable, Union, List

from common import constants


class Float(float):
    def __eq__(self, other):
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
    def average(values: List[float]) -> Float:
        if len(values) == 0:
            return O
        total = Float.sum([values[i] for i in range(len(values))])
        return total / len(values)


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
    if days <= 0:
        return f'{int(days)}d'
    sizes = [1, constants.WEEK, constants.MONTH, constants.YEAR]
    postfix = ['d', 'wk', 'mon', 'yr']
    numbers = {}
    remainder = days
    for i in reversed(range(len(sizes))):
        if remainder >= sizes[i]:
            numbers[postfix[i]] = remainder // sizes[i]
            remainder -= numbers[postfix[i]] * sizes[i]
    return ' '.join([f'{n}{p}' for p, n in numbers.items()])


def human_format(num: Union[float, int]) -> str:
    num = float('{:.3g}'.format(num))
    magnitude = 0
    postfix = ['', 'K', 'M', 'B', 'T']
    while abs(num) >= 1000 and magnitude < len(postfix) - 1:
        magnitude += 1
        num /= 1000.0
    deci = 1 if abs(num) > 2 else 2
    return '{}{}'.format('{:.{deci}f}'.format(num, deci=deci).rstrip('0').rstrip('.'), postfix[magnitude])


Percent = Float
Ratio = Float
Date = Duration
Stock = Int
Dollar = Float
O = Float(0)
O_INT = Int(0)
ONE = Float(1)
TWO = Float(2)
ONE_INT = Duration(1)
TWO_INT = Duration(2)
