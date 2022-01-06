from dataclasses import is_dataclass
from enum import Enum
from typing import Any

from common.context import DataGenerator

NEXT_ID = {}


def generate_id(obj) -> str:
    class_name = obj.__class__.__name__
    id_count = NEXT_ID[class_name] if class_name in NEXT_ID else 1
    NEXT_ID[class_name] = id_count + 1
    return f'{class_name}_{id_count}'


class Primitive:
    def __init__(self, data_generator: DataGenerator):
        self.id = generate_id(self)
        self.data_generator = data_generator

    def str_type_encoder(self, value: Any) -> str:
        if (isinstance(value, str) or isinstance(value, int) or is_dataclass(value)
                or isinstance(value, bool) or isinstance(value, Enum)):
            return str(value)
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

    def __eq__(self, other):
        if isinstance(other, Primitive):
            if self.id == other.id:
                return True
        return False
