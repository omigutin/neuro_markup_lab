"""
Схема атрибутов фигур документа.

Известные поля (``label``, ``wz``, ``group_id`` …) и их тип, подпись и подсказка берутся из модели
:class:`MarkupShape`. Прочие поля — поля документа: их тип один на все фигуры документа
и выводится из значений либо задаётся редактором.
"""

__all__ = ['MarkupAttributeSchema']

import re
import types
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from enum import Enum
from typing import Any, Union, get_args, get_origin

from pydantic.fields import FieldInfo

from .markup_coercion import coerce_value
from .markup_shape import MarkupShape
from .markup_types import SHAPE_RESERVED_KEYS, AttributeSpec, AttributeType, EditorField, JsonValue

# Имя атрибута: латиница в нижнем регистре, цифры и подчёркивание, не с цифры
_ATTRIBUTE_NAME_RE = re.compile(r'^[a-z_][a-z0-9_]*$')

# Тип значения поля модели → тип атрибута редактора
_PLAIN_TYPES: tuple[tuple[type, AttributeType], ...] = (
    (bool, AttributeType.BOOL), (int, AttributeType.INT), (float, AttributeType.FLOAT),
    (str, AttributeType.STR), (dict, AttributeType.DICT),
)


def _spec_from_field(name: str, info: FieldInfo) -> AttributeSpec:
    """ Описание атрибута по полю модели фигуры. """
    editor = next((m for m in info.metadata if isinstance(m, EditorField)), None)
    if editor is None:
        raise TypeError(f'MarkupShape field {name!r} has no EditorField')
    annotation, nullable = _unwrap_optional(info.annotation)
    title, hint = info.title or '', info.description or ''
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        excluded = {m.value for m in editor.excluded}
        return AttributeSpec(
            name, AttributeType.STR, nullable=nullable, known=True, required=editor.required, strict=True,
            choices=tuple(m.value for m in annotation if m.value not in excluded),
            deprecated=tuple(m.value for m in editor.deprecated), title=title, hint=hint, hidden=editor.hidden)
    if annotation is Any:
        return AttributeSpec(name, AttributeType.ANY, nullable=True, known=True, required=editor.required,
                             title=title, hint=hint, hidden=editor.hidden)
    origin = get_origin(annotation) or annotation
    for plain, attribute_type in _PLAIN_TYPES:
        if origin is plain:
            return AttributeSpec(name, attribute_type, nullable=nullable, known=True, required=editor.required,
                                 title=title, hint=hint, hidden=editor.hidden)
    raise TypeError(f'Unsupported MarkupShape field type for {name!r}: {annotation!r}')


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """ ``X | None`` → ``(X, True)``; прочие типы — ``(тип, False)``. """
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def _known_specs() -> tuple[AttributeSpec, ...]:
    """ Известные поля в порядке показа в редакторе: все поля модели фигуры, кроме геометрии. """
    fields = [(name, info) for name, info in MarkupShape.model_fields.items() if name not in SHAPE_RESERVED_KEYS]
    fields.sort(key=lambda item: _editor_order(item[0], item[1]))
    return tuple(_spec_from_field(name, info) for name, info in fields)


def _editor_order(name: str, info: FieldInfo) -> int:
    editor = next((m for m in info.metadata if isinstance(m, EditorField)), None)
    if editor is None:
        raise TypeError(f'MarkupShape field {name!r} has no EditorField')
    return editor.order


# Известные поля модели фигуры
_KNOWN_SPECS: tuple[AttributeSpec, ...] = _known_specs()
_KNOWN_BY_NAME: dict[str, AttributeSpec] = {spec.name: spec for spec in _KNOWN_SPECS}

# Подсказка для своих полей документа
_DOCUMENT_FIELD_HINT = 'Своё поле документа: в модели фигуры его нет, читается по имени.'

# Порядок выбора типа поля документа по значениям: первый тип, к которому приводятся все значения
_INFERENCE_ORDER: tuple[AttributeType, ...] = (
    AttributeType.BOOL, AttributeType.INT, AttributeType.FLOAT, AttributeType.DICT, AttributeType.STR,
)


class MarkupAttributeSchema:
    """ Схема атрибутов одного документа: известные поля модели фигуры и поля документа. """

    def __init__(self, document_fields: Mapping[str, AttributeSpec] | None = None) -> None:
        # Поля документа (которых нет в модели фигуры): имя → описание
        self._document_fields: dict[str, AttributeSpec] = {
            name: spec for name, spec in (document_fields or {}).items() if name not in _KNOWN_BY_NAME
        }

    @staticmethod
    def known_specs() -> tuple[AttributeSpec, ...]:
        """ Известные поля модели фигуры в порядке показа в редакторе. """
        return _KNOWN_SPECS

    @staticmethod
    def is_valid_name(name: object) -> bool:
        """ Имя атрибута допустимо: латиница в нижнем регистре, цифры, ``_``; не геометрия. """
        return (isinstance(name, str) and bool(_ATTRIBUTE_NAME_RE.match(name))
                and name not in SHAPE_RESERVED_KEYS)

    @property
    def document_fields(self) -> dict[str, AttributeSpec]:
        """ Поля документа (копия). """
        return dict(self._document_fields)

    def spec(self, name: str) -> AttributeSpec | None:
        """ Описание поля по имени или ``None``, если поле неизвестно схеме. """
        return _KNOWN_BY_NAME.get(name) or self._document_fields.get(name)

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            'known': [spec.as_dict() for spec in _KNOWN_SPECS],
            'document': [spec.as_dict() for spec in self._document_fields.values()],
        }

    @classmethod
    def for_shapes(cls, shapes: Iterable[Mapping[str, JsonValue]],
                   overrides: Mapping[str, AttributeSpec] | None = None) -> 'MarkupAttributeSchema':
        """
            Схема документа: для полей, которых нет среди известных, тип выводится из значений
            всех фигур. ``overrides`` — типы полей, заданные редактором; имеют приоритет.
        """
        values: dict[str, list[JsonValue]] = {}
        for shape in shapes:
            for key, value in shape.items():
                if key in SHAPE_RESERVED_KEYS or key in _KNOWN_BY_NAME:
                    continue
                values.setdefault(key, []).append(value)
        fields: dict[str, AttributeSpec] = {}
        for name, items in values.items():
            fields[name] = _infer_spec(name, items)
        for name, spec in (overrides or {}).items():
            if name not in _KNOWN_BY_NAME:
                fields[name] = spec if spec.hint else replace(spec, hint=_DOCUMENT_FIELD_HINT)
        return cls(fields)


def _infer_spec(name: str, values: list[JsonValue]) -> AttributeSpec:
    """ Тип поля документа: первый тип из ``_INFERENCE_ORDER``, к которому приводятся все значения. """
    present = [v for v in values if v is not None]
    nullable = len(present) != len(values)
    if not present:
        return AttributeSpec(name, AttributeType.STR, nullable=True, hint=_DOCUMENT_FIELD_HINT)
    for candidate in _INFERENCE_ORDER:
        probe = AttributeSpec(name, candidate, nullable=True)
        if all(coerce_value(probe, v)[0] for v in present) and _keeps_kind(candidate, present):
            return AttributeSpec(name, candidate, nullable=nullable, hint=_DOCUMENT_FIELD_HINT)
    return AttributeSpec(name, AttributeType.ANY, nullable=True, hint=_DOCUMENT_FIELD_HINT)


def _keeps_kind(candidate: AttributeType, values: Sequence[JsonValue]) -> bool:
    """
        Вывод типа не должен менять смысл значений: bool выбираем, только если есть настоящие
        bool, а числа — только если есть настоящие числа (строки ``"1"`` сами по себе остаются str).
    """
    if candidate == AttributeType.BOOL:
        return any(isinstance(v, bool) for v in values)
    if candidate in (AttributeType.INT, AttributeType.FLOAT):
        return any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
    return True
