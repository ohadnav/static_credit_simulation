from __future__ import annotations

from dataclasses import is_dataclass
from enum import Enum
from typing import Any, Tuple

from common.context import DataGenerator
from common.local_numbers import Float, Int

NEXT_ID = {}


def generate_id(obj) -> Tuple[str, int]:
    class_name = obj.__class__.__name__
    id_count = NEXT_ID[class_name] if class_name in NEXT_ID else 1
    NEXT_ID[class_name] = id_count + 1
    return id_name(obj, id_count), id_count


def id_name(obj, int_id: int) -> str:
    class_name = obj.__class__.__name__
    return f'{class_name}_{int_id}'


class Primitive:
    def __init__(self, data_generator: DataGenerator):
        self.id, self.int_id = generate_id(self)
        self.data_generator = data_generator

    def set_id(self, int_id: int):
        self.int_id = int_id
        self.id = id_name(self, int_id)

    def reset_id(self):
        self.id, self.int_id = generate_id(self)

    def copy_id(self, source: Primitive):
        self.set_id(source.int_id)

    def str_type_encoder(self, value: Any) -> str:
        if (isinstance(value, str) or isinstance(value, int) or isinstance(value, Float) or isinstance(
                value, Int) or is_dataclass(value) or isinstance(value, bool) or isinstance(value, Enum)):
            return value.__str__()
        elif isinstance(value, float):
            return str(round(value, 2))
        elif value is None:
            return 'None'
        elif isinstance(value, Primitive):
            return value.id
        else:
            return type(value).__name__

    def __str__(self):
        s = ''
        for name, value in vars(self).items():
            s += f' {name}={self.str_type_encoder(value)}'
        return s

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other: Primitive):
        if isinstance(other, Primitive):
            if self.id == other.id:
                return True
        return False
