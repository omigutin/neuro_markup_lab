""" Приведение одного значения к типу поля. """

import pytest

from neuro_markup_lab.markup import AttributeSpec, AttributeType, coerce_value
from neuro_markup_lab.markup.markup_coercion import same_value


def spec(type_: AttributeType, nullable: bool = False) -> AttributeSpec:
    return AttributeSpec('f', type_, nullable=nullable)


@pytest.mark.parametrize('value, expected', [
    (3, 3), ('3', 3), (' 4 ', 4), (2.0, 2), ('5.0', 5), (-1, -1),
])
def test_int_converts(value, expected):
    ok, result = coerce_value(spec(AttributeType.INT), value)
    assert ok and result == expected and type(result) is int


@pytest.mark.parametrize('value', ['abc', 2.5, True, [], {}, '', None])
def test_int_rejects(value):
    assert coerce_value(spec(AttributeType.INT), value)[0] is False


def test_nullable_int_takes_empty_string_and_none_as_null():
    assert coerce_value(spec(AttributeType.INT, True), '') == (True, None)
    assert coerce_value(spec(AttributeType.INT, True), None) == (True, None)


def test_float():
    assert coerce_value(spec(AttributeType.FLOAT), 2) == (True, 2.0)
    assert coerce_value(spec(AttributeType.FLOAT), '1.5') == (True, 1.5)
    assert coerce_value(spec(AttributeType.FLOAT), 'nan')[0] is False
    assert coerce_value(spec(AttributeType.FLOAT), False)[0] is False


def test_str():
    assert coerce_value(spec(AttributeType.STR), 5) == (True, '5')
    assert coerce_value(spec(AttributeType.STR), True) == (True, 'true')
    # Пустая строка остаётся строкой даже в поле с null
    assert coerce_value(spec(AttributeType.STR, True), '') == (True, '')
    # Не допускающее null строковое поле: null → ''
    assert coerce_value(spec(AttributeType.STR), None) == (True, '')
    assert coerce_value(spec(AttributeType.STR), {'a': 1})[0] is False


@pytest.mark.parametrize('value, expected', [(True, True), ('false', False), ('1', True), (0, False), (' Yes ', True)])
def test_bool_converts(value, expected):
    assert coerce_value(spec(AttributeType.BOOL), value) == (True, expected)


@pytest.mark.parametrize('value', [2, 'maybe', None, 1.0])
def test_bool_rejects(value):
    assert coerce_value(spec(AttributeType.BOOL), value)[0] is False


def test_dict_and_any():
    assert coerce_value(spec(AttributeType.DICT), None) == (True, {})
    assert coerce_value(spec(AttributeType.DICT), {'a': 1}) == (True, {'a': 1})
    assert coerce_value(spec(AttributeType.DICT), [1])[0] is False
    assert coerce_value(spec(AttributeType.ANY), [1, 'x']) == (True, [1, 'x'])


def test_same_value_compares_types():
    assert same_value(1, 1)
    assert not same_value(1, 1.0)
    assert not same_value(1, True)
    assert not same_value('1', 1)
