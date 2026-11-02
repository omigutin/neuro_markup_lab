""" Модель фигуры: известные поля, поля из редактора, запись без потерь. """

import pytest
from pydantic import ValidationError

from neuro_markup_lab.markup import MarkupShape, ShapeLabel, ShapePosition, ShapeType


def test_known_fields_are_typed():
    shape = MarkupShape.model_validate({'label': 'crop', 'position': 'left', 'wz': '2', 'shape_type': 'rectangle',
                                        'points': [[0, 0], [1, 1]]})
    assert shape.label is ShapeLabel.CROP and shape.position is ShapePosition.LEFT
    assert shape.wz == 2 and shape.shape_type is ShapeType.RECTANGLE


def test_defaults():
    shape = MarkupShape()
    assert shape.label is ShapeLabel.SEARCH and shape.position is ShapePosition.NONE
    assert shape.show is True and shape.flags == {} and shape.points == []


def test_unknown_label_rejected():
    with pytest.raises(ValidationError):
        MarkupShape.model_validate({'label': 'zone'})


def test_editor_fields_are_kept_and_readable():
    shape = MarkupShape.model_validate({'label': 'input', 'zone_kind': 'a', 'speed': 3})
    assert shape.attribute('zone_kind') == 'a' and shape.attribute('speed') == 3
    assert shape.attribute('label') is ShapeLabel.INPUT
    assert shape.attribute('missing', 'x') == 'x'
    assert shape.model_dump(mode='json')['zone_kind'] == 'a'
