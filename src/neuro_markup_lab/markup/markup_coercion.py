"""
Приведение одного значения атрибута к типу поля.

``"3"`` → ``3`` для int, ``""`` → ``null`` для поля, допускающего null, ``"true"`` → ``True``
для bool. Значение, которое привести нельзя, возвращается как есть с признаком ``False``.
"""

__all__ = ['coerce_value', 'same_value']

import math

from .markup_types import AttributeSpec, AttributeType, JsonValue

# Строковые записи логических значений
_TRUE_STRINGS: frozenset[str] = frozenset({'true', '1', 'yes'})
_FALSE_STRINGS: frozenset[str] = frozenset({'false', '0', 'no'})


def coerce_value(spec: AttributeSpec, value: JsonValue) -> tuple[bool, JsonValue]:
    """ ``(True, приведённое значение)`` или ``(False, value)``, если привести нельзя. """
    if spec.type == AttributeType.ANY:
        return True, value
    if value is None:
        return _coerce_none(spec)
    # Пустая строка в числовом/логическом поле с null — это «нет значения»
    if isinstance(value, str) and not value.strip() and spec.nullable and spec.type != AttributeType.STR:
        return True, None
    return _CONVERTERS[spec.type](value)


def _coerce_none(spec: AttributeSpec) -> tuple[bool, JsonValue]:
    if spec.nullable:
        return True, None
    if spec.type == AttributeType.STR:
        return True, ''
    if spec.type == AttributeType.DICT:
        return True, {}
    return False, None


def _to_int(value: JsonValue) -> tuple[bool, JsonValue]:
    if isinstance(value, bool):
        return False, value
    if isinstance(value, int):
        return True, value
    if isinstance(value, float):
        return (True, int(value)) if math.isfinite(value) and value.is_integer() else (False, value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return True, int(text)
        except ValueError:
            pass
        try:
            number = float(text)
        except ValueError:
            return False, value
        return (True, int(number)) if math.isfinite(number) and number.is_integer() else (False, value)
    return False, value


def _to_float(value: JsonValue) -> tuple[bool, JsonValue]:
    if isinstance(value, bool):
        return False, value
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return False, value
    else:
        return False, value
    return (True, number) if math.isfinite(number) else (False, value)


def _to_str(value: JsonValue) -> tuple[bool, JsonValue]:
    if isinstance(value, str):
        return True, value
    if isinstance(value, bool):
        return True, 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return True, str(value)
    return False, value


def _to_bool(value: JsonValue) -> tuple[bool, JsonValue]:
    if isinstance(value, bool):
        return True, value
    if isinstance(value, int) and value in (0, 1):
        return True, bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE_STRINGS:
            return True, True
        if text in _FALSE_STRINGS:
            return True, False
    return False, value


def _to_dict(value: JsonValue) -> tuple[bool, JsonValue]:
    return (True, value) if isinstance(value, dict) else (False, value)


_CONVERTERS = {
    AttributeType.INT: _to_int,
    AttributeType.FLOAT: _to_float,
    AttributeType.STR: _to_str,
    AttributeType.BOOL: _to_bool,
    AttributeType.DICT: _to_dict,
}


def same_value(before: JsonValue, after: JsonValue) -> bool:
    """ Значение не изменилось, включая тип (``1`` и ``1.0`` и ``True`` — разные значения). """
    return type(before) is type(after) and before == after
