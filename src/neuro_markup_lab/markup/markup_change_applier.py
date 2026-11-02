"""
Применение правок редактора к исходному LabelMe JSON.

Меняется только переданное: геометрия (``points``, ``shape_type``) и набор атрибутов фигуры.
Порядок ключей фигуры сохраняется: изменённые остаются на своих местах, новые добавляются
в конец, удалённые убираются. Поля документа и непереданные фигуры не трогаются.
"""

__all__ = ['MarkupChangeApplier']

from collections.abc import Mapping, MutableMapping, Sequence

from .markup_attribute_schema import MarkupAttributeSchema
from .markup_error import MarkupError
from .markup_types import FIXED_POINTS_SHAPE_TYPES, SHAPE_RESERVED_KEYS, SHAPE_TYPE_MIN_POINTS, JsonValue, ShapeChange


class MarkupChangeApplier:
    """ Применяет правки фигур к документу на месте. """

    def apply(self, document: MutableMapping[str, JsonValue], changes: Mapping[int, ShapeChange]) -> None:
        """ Применяет ``changes`` (индекс фигуры в ``shapes[]`` → правка) к ``document``. """
        shapes = document.get('shapes')
        if not isinstance(shapes, list):
            raise MarkupError('Markup document has no shapes list')
        for index, change in changes.items():
            shape = shapes[index] if 0 <= index < len(shapes) else None
            if not isinstance(shape, dict):
                raise MarkupError(f'Shape {index} not found in markup document')
            self._apply_geometry(shape, index, change)
            if change.attributes is not None:
                shapes[index] = self._merge_attributes(shape, index, change.attributes)

    @staticmethod
    def _apply_geometry(shape: dict[str, JsonValue], index: int, change: ShapeChange) -> None:
        if change.points is None and change.shape_type is None:
            return
        shape_type = change.shape_type if change.shape_type is not None else shape.get('shape_type')
        if not isinstance(shape_type, str) or shape_type not in SHAPE_TYPE_MIN_POINTS:
            raise MarkupError(f'Shape {index}: unknown shape type {shape_type!r}')
        points = _normalize_points(change.points) if change.points is not None else shape.get('points')
        if points is None or not isinstance(points, list):
            raise MarkupError(f'Shape {index}: invalid points')
        _check_points_count(index, shape_type, points)
        shape['points'] = points
        shape['shape_type'] = shape_type

    @staticmethod
    def _merge_attributes(shape: dict[str, JsonValue], index: int,
                          attributes: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        for name in attributes:
            if name in SHAPE_RESERVED_KEYS:
                raise MarkupError(f'Shape {index}: {name!r} is geometry, not an attribute')
            if name not in shape and not MarkupAttributeSchema.is_valid_name(name):
                raise MarkupError(f'Shape {index}: invalid attribute name {name!r}')
        for spec in MarkupAttributeSchema.known_specs():
            if spec.required and spec.name in shape and spec.name not in attributes:
                raise MarkupError(f'Shape {index}: attribute {spec.name!r} cannot be removed')
        merged: dict[str, JsonValue] = {}
        for key, value in shape.items():
            if key in SHAPE_RESERVED_KEYS:
                merged[key] = value
            elif key in attributes:
                merged[key] = attributes[key]
        for key, value in attributes.items():
            if key not in merged:
                merged[key] = value
        return merged


def _check_points_count(index: int, shape_type: str, points: Sequence[JsonValue]) -> None:
    """ Точек достаточно для типа фигуры (полигон — от 3, прямоугольник — ровно 2 и т.п.). """
    minimum = SHAPE_TYPE_MIN_POINTS[shape_type]
    count = len(points)
    if count < minimum or (shape_type in FIXED_POINTS_SHAPE_TYPES and count != minimum):
        raise MarkupError(f'Shape {index} ({shape_type}): wrong number of points: {count}')


def _normalize_points(points: object) -> list[JsonValue] | None:
    """ ``[[x, y], ...]`` из чисел либо ``None`` при некорректной структуре. Точность не урезаем. """
    if not isinstance(points, list) or not points:
        return None
    result: list[JsonValue] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        x, y = point[0], point[1]
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) \
                or not isinstance(y, (int, float)):
            return None
        result.append([float(x), float(y)])
    return result
