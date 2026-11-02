"""
Приведение типов атрибутов фигур к схеме документа.

Каждое значение приводится к типу своего поля: ``"3"`` → ``3`` для int, ``""`` → ``null``
для поля, допускающего null. То, что привести нельзя (``wz: "abc"``), попадает в проблемы —
такой документ не сохраняется, пока значение не исправят вручную.
"""

__all__ = ['MarkupNormalizer']

from collections.abc import MutableMapping

from .markup_attribute_schema import MarkupAttributeSchema
from .markup_coercion import coerce_value, same_value
from .markup_types import SHAPE_RESERVED_KEYS, JsonValue, NormalizationReport, ValueConversion, ValueProblem


class MarkupNormalizer:
    """ Приводит атрибуты всех фигур документа к типам схемы. """

    def __init__(self, schema: MarkupAttributeSchema) -> None:
        self._schema = schema

    def normalize(self, document: MutableMapping[str, JsonValue]) -> NormalizationReport:
        """
            Приводит значения атрибутов фигур ``document`` на месте и возвращает отчёт.
            Значения с проблемами не меняются.
        """
        report = NormalizationReport()
        shapes = document.get('shapes')
        if not isinstance(shapes, list):
            return report
        for index, shape in enumerate(shapes):
            if not isinstance(shape, dict):
                continue
            label = str(shape.get('label') or '')
            for key in list(shape.keys()):
                if key in SHAPE_RESERVED_KEYS:
                    continue
                spec = self._schema.spec(key)
                if spec is None:
                    continue
                before = shape[key]
                ok, after = coerce_value(spec, before)
                if not ok or not spec.accepts(after):
                    report.problems.append(ValueProblem(index, label, key, before, spec.expected))
                elif not same_value(before, after):
                    shape[key] = after
                    report.conversions.append(ValueConversion(index, label, key, before, after))
        return report
