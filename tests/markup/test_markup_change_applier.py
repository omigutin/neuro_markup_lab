""" Применение правок редактора к исходному документу. """

import pytest

from neuro_markup_lab.markup import MarkupChangeApplier, MarkupError, ShapeChange


def document() -> dict:
    return {'version': '5.5.0', 'shapes': [
        {'label': 'crop', 'points': [[10, 20], [110, 220]], 'group_id': 2, 'shape_type': 'rectangle', 'flags': {}},
        {'label': 'input', 'points': [[0, 0], [1, 0], [1, 1]], 'shape_type': 'polygon'},
    ], 'imageData': None}


def test_geometry_change_keeps_other_fields():
    doc = document()
    MarkupChangeApplier().apply(doc, {0: ShapeChange(points=[[1, 1], [9, 1], [9, 9]], shape_type='polygon')})
    shape = doc['shapes'][0]
    assert shape['shape_type'] == 'polygon' and shape['points'] == [[1.0, 1.0], [9.0, 1.0], [9.0, 9.0]]
    assert shape['group_id'] == 2 and doc['shapes'][1] == document()['shapes'][1]
    assert doc['imageData'] is None and doc['version'] == '5.5.0'


def test_attributes_replace_set_in_place_and_append_new():
    doc = document()
    MarkupChangeApplier().apply(doc, {0: ShapeChange(attributes={'label': 'crop2', 'flags': {}, 'zone_kind': 'a'})})
    shape = doc['shapes'][0]
    # group_id удалён, label на месте, новое поле — в конце; геометрия на своих местах
    assert list(shape) == ['label', 'points', 'shape_type', 'flags', 'zone_kind']
    assert shape['label'] == 'crop2'


def test_label_cannot_be_removed():
    with pytest.raises(MarkupError):
        MarkupChangeApplier().apply(document(), {0: ShapeChange(attributes={'group_id': 1})})


@pytest.mark.parametrize('name', ['Zone', 'зона', 'zone kind'])
def test_new_attribute_name_validated(name):
    with pytest.raises(MarkupError):
        MarkupChangeApplier().apply(document(), {0: ShapeChange(attributes={'label': 'x', name: 1})})


def test_existing_odd_name_is_kept():
    doc = document()
    doc['shapes'][1]['oldName'] = 1
    MarkupChangeApplier().apply(doc, {1: ShapeChange(attributes={'label': 'input', 'oldName': 2})})
    assert doc['shapes'][1]['oldName'] == 2


def test_geometry_keys_are_not_attributes():
    with pytest.raises(MarkupError):
        MarkupChangeApplier().apply(document(), {0: ShapeChange(attributes={'label': 'x', 'points': []})})


@pytest.mark.parametrize('change', [
    ShapeChange(points=[[1, 1]], shape_type='polygon'),
    ShapeChange(points=[[1, 1], [2, 2], [3, 3]], shape_type='rectangle'),
    ShapeChange(shape_type='hexagon'),
    ShapeChange(points=[[1, 'x'], [2, 2]]),
    ShapeChange(points=[[True, 1], [2, 2]]),
    ShapeChange(points=[]),
])
def test_invalid_geometry(change):
    with pytest.raises(MarkupError):
        MarkupChangeApplier().apply(document(), {0: change})


def test_unknown_shape_index():
    with pytest.raises(MarkupError):
        MarkupChangeApplier().apply(document(), {5: ShapeChange(attributes={'label': 'x'})})


def test_document_without_shapes():
    with pytest.raises(MarkupError):
        MarkupChangeApplier().apply({'version': '1'}, {0: ShapeChange()})
