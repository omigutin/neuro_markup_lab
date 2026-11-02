""" Схема атрибутов: известные поля из модели фигуры, имена полей, вывод типа полей документа. """

import pytest

from neuro_markup_lab.markup import (
    SHAPE_RESERVED_KEYS,
    AttributeSpec,
    AttributeType,
    MarkupAttributeSchema,
    MarkupShape,
)


def test_known_fields_are_model_fields():
    # Известные поля схемы — все поля модели фигуры, кроме геометрии
    names = {spec.name for spec in MarkupAttributeSchema.known_specs()}
    assert names == set(MarkupShape.model_fields) - SHAPE_RESERVED_KEYS
    assert all(spec.known for spec in MarkupAttributeSchema.known_specs())


def test_known_fields_order():
    names = [spec.name for spec in MarkupAttributeSchema.known_specs()]
    assert names == ['label', 'group_id', 'wz', 'position', 'markup', 'show', 'description', 'flags', 'mask']


def test_known_types_from_model():
    expected = {'wz': AttributeType.INT, 'group_id': AttributeType.INT, 'markup': AttributeType.INT,
                'show': AttributeType.BOOL, 'label': AttributeType.STR, 'position': AttributeType.STR,
                'description': AttributeType.STR, 'flags': AttributeType.DICT, 'mask': AttributeType.ANY}
    schema = MarkupAttributeSchema()
    for name, type_ in expected.items():
        assert schema.spec(name).type == type_
    assert schema.spec('wz').nullable and schema.spec('description').nullable
    assert not schema.spec('show').nullable and not schema.spec('flags').nullable


def test_titles_and_hints_from_model():
    spec = MarkupAttributeSchema().spec('wz')
    info = MarkupShape.model_fields['wz']
    assert (spec.title, spec.hint) == (info.title, info.description)


def test_label_is_required_and_has_choices():
    label = MarkupAttributeSchema().spec('label')
    assert label.required and 'crop' in label.choices and 'automarkup' in label.choices


@pytest.mark.parametrize('name', ['wz', 'zone_kind', '_x', 'a1'])
def test_valid_names(name):
    assert MarkupAttributeSchema.is_valid_name(name)


@pytest.mark.parametrize('name', ['', 'Zone', 'зона', 'zone kind', '1zone', 'zone-kind', 'points', 'shape_type',
                                  None, 5])
def test_invalid_names(name):
    assert not MarkupAttributeSchema.is_valid_name(name)


def test_infers_document_field_types():
    shapes = [
        {'label': 'a', 'points': [], 'count': 1, 'ratio': 1, 'kind': 'x', 'on': True, 'extra': {'a': 1},
         'tags': [1]},
        {'label': 'b', 'points': [], 'count': '2', 'ratio': 0.5, 'kind': None, 'on': 'false', 'extra': {}, 'tags': [2]},
    ]
    fields = MarkupAttributeSchema.for_shapes(shapes).document_fields
    assert fields['count'].type == AttributeType.INT and not fields['count'].nullable
    assert fields['ratio'].type == AttributeType.FLOAT
    assert fields['kind'].type == AttributeType.STR and fields['kind'].nullable
    assert fields['on'].type == AttributeType.BOOL
    assert fields['extra'].type == AttributeType.DICT
    assert fields['tags'].type == AttributeType.ANY
    assert 'label' not in fields and 'points' not in fields


def test_numeric_strings_alone_stay_strings():
    fields = MarkupAttributeSchema.for_shapes([{'code': '1'}, {'code': '2'}]).document_fields
    assert fields['code'].type == AttributeType.STR


def test_mixed_kinds_fall_back_to_str():
    fields = MarkupAttributeSchema.for_shapes([{'code': 'abc'}, {'code': 5}]).document_fields
    assert fields['code'].type == AttributeType.STR


def test_overrides_win_but_not_for_known_fields():
    overrides = {'code': AttributeSpec('code', AttributeType.INT, nullable=True),
                 'wz': AttributeSpec('wz', AttributeType.STR, nullable=False)}
    schema = MarkupAttributeSchema.for_shapes([{'code': 'abc'}], overrides)
    assert schema.spec('code').type == AttributeType.INT
    assert schema.spec('wz').type == AttributeType.INT


def test_as_dict_lists_known_and_document_fields():
    data = MarkupAttributeSchema.for_shapes([{'zone_kind': 'a'}]).as_dict()
    assert [s['name'] for s in data['document']] == ['zone_kind']
    assert any(s['name'] == 'label' and s['required'] for s in data['known'])


def test_label_and_position_are_strict_enums():
    schema = MarkupAttributeSchema()
    label, position = schema.spec('label'), schema.spec('position')
    assert label.strict and position.strict
    assert set(label.deprecated) == {'search', 'promt'} and '' not in label.choices
    assert set(position.choices) == {'', 'left', 'right', 'top', 'bottom', 'centre'}


def test_known_fields_have_hints_and_mask_hidden():
    for spec in MarkupAttributeSchema.known_specs():
        assert spec.hint, spec.name
    assert MarkupAttributeSchema().spec('mask').hidden
    assert not MarkupAttributeSchema().spec('wz').hidden


def test_document_fields_get_hint():
    overrides = {'side': AttributeSpec('side', AttributeType.STR, nullable=True)}
    schema = MarkupAttributeSchema.for_shapes([{'zone_kind': 'a'}], overrides)
    assert schema.spec('zone_kind').hint and schema.spec('side').hint
