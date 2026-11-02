"""
Модель разметки: схема атрибутов фигур, приведение типов и применение правок.

Формат разметки — LabelMe JSON. Модели :class:`MarkupDocument` и :class:`MarkupShape` описывают
известные поля; редактор работает с документом как с ``dict``, поэтому неизвестные поля документа
и фигур сохраняются без изменений.
"""

__all__ = [
    'SHAPE_RESERVED_KEYS',
    'SHAPE_TYPE_MIN_POINTS',
    'AttributeSpec',
    'AttributeType',
    'EditorField',
    'JsonValue',
    'MarkupAttributeSchema',
    'MarkupChangeApplier',
    'MarkupDocument',
    'MarkupError',
    'MarkupNormalizer',
    'MarkupShape',
    'NormalizationReport',
    'ShapeChange',
    'ShapeLabel',
    'ShapePosition',
    'ShapeType',
    'ValueConversion',
    'ValueProblem',
    'coerce_value',
]

from .markup_attribute_schema import MarkupAttributeSchema
from .markup_change_applier import MarkupChangeApplier
from .markup_coercion import coerce_value
from .markup_document import MarkupDocument
from .markup_error import MarkupError
from .markup_normalizer import MarkupNormalizer
from .markup_shape import MarkupShape
from .markup_types import (
    SHAPE_RESERVED_KEYS,
    SHAPE_TYPE_MIN_POINTS,
    AttributeSpec,
    AttributeType,
    EditorField,
    JsonValue,
    NormalizationReport,
    ShapeChange,
    ShapeLabel,
    ShapePosition,
    ShapeType,
    ValueConversion,
    ValueProblem,
)
