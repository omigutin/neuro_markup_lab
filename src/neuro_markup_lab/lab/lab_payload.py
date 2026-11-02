""" Разбор тела запроса сохранения из редактора в :class:`SaveRequest`. """

__all__ = ['parse_save_request']

from collections.abc import Mapping
from pathlib import Path

from ..markup import AttributeSpec, AttributeType, JsonValue, MarkupAttributeSchema, MarkupError, ShapeChange
from ..storage import MarkupVariant
from .lab_types import SaveRequest

# Типы, которые редактор может задать полю документа
_EDITABLE_FIELD_TYPES: frozenset[AttributeType] = frozenset({
    AttributeType.INT, AttributeType.FLOAT, AttributeType.STR, AttributeType.BOOL, AttributeType.DICT,
})


def parse_save_request(payload: Mapping[str, JsonValue]) -> SaveRequest:
    """ Запрос сохранения из JSON тела. Некорректные данные — :class:`MarkupError`. """
    video = payload.get('video')
    if not isinstance(video, str) or not video.strip():
        raise MarkupError('Field "video" is required')
    jsons_dir = payload.get('jsons_dir') or ''
    if not isinstance(jsons_dir, str):
        raise MarkupError('Field "jsons_dir" must be a string')
    return SaveRequest(
        video=Path(video.strip()),
        base_variant=_variant(payload.get('base_variant'), 'base_variant'),
        target_variant=_variant(payload.get('target_variant'), 'target_variant'),
        jsons_dir=jsons_dir.strip(),
        changes=_changes(payload.get('changes')),
        fields=_fields(payload.get('fields')),
        dry_run=payload.get('dry_run') is True,
        confirm_production=payload.get('confirm_production') is True,
    )


def _variant(value: JsonValue, name: str) -> MarkupVariant:
    try:
        return MarkupVariant(value)
    except ValueError as exc:
        raise MarkupError(f'Field "{name}" has unknown markup variant {value!r}') from exc


def _changes(raw: JsonValue) -> dict[int, ShapeChange]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise MarkupError('Field "changes" must be an object')
    changes: dict[int, ShapeChange] = {}
    for key, item in raw.items():
        try:
            index = int(key)
        except ValueError as exc:
            raise MarkupError(f'Invalid shape index {key!r}') from exc
        if not isinstance(item, dict):
            raise MarkupError(f'Shape {index}: change must be an object')
        attributes = item.get('attributes')
        if attributes is not None and not isinstance(attributes, dict):
            raise MarkupError(f'Shape {index}: attributes must be an object')
        shape_type = item.get('shape_type')
        if shape_type is not None and not isinstance(shape_type, str):
            raise MarkupError(f'Shape {index}: shape_type must be a string')
        points = item.get('points')
        if points is not None and not isinstance(points, list):
            raise MarkupError(f'Shape {index}: points must be a list')
        changes[index] = ShapeChange(points=points, shape_type=shape_type, attributes=attributes)
    return changes


def _fields(raw: JsonValue) -> dict[str, AttributeSpec]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise MarkupError('Field "fields" must be an object')
    fields: dict[str, AttributeSpec] = {}
    for name, item in raw.items():
        if not MarkupAttributeSchema.is_valid_name(name):
            raise MarkupError(f'Invalid attribute name {name!r}')
        if not isinstance(item, dict):
            raise MarkupError(f'Field {name!r}: description must be an object')
        try:
            field_type = AttributeType(item.get('type'))
        except ValueError as exc:
            raise MarkupError(f'Field {name!r}: unknown type {item.get("type")!r}') from exc
        if field_type not in _EDITABLE_FIELD_TYPES:
            raise MarkupError(f'Field {name!r}: type {field_type.value!r} cannot be set')
        fields[name] = AttributeSpec(name, field_type, nullable=item.get('nullable') is True)
    return fields
