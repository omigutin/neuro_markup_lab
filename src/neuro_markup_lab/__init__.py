"""
neuro_markup_lab — редактор разметки зон (LabelMe JSON) по кадру видео.

Библиотека: формат разметки (:class:`MarkupDocument`, :class:`MarkupShape`, перечисления меток
и положений), схема и приведение типов атрибутов, источники разметки видео. Веб-интерфейс —
подпакет :mod:`neuro_markup_lab.web`, ставится отдельно (часть ``[web]``).
"""

from .lab import MarkupLabService
from .markup import (
    AttributeSpec,
    AttributeType,
    MarkupAttributeSchema,
    MarkupDocument,
    MarkupError,
    MarkupShape,
    ShapeLabel,
    ShapePosition,
    ShapeType,
)
from .storage import (
    CameraKey,
    CameraNameParser,
    CameraResolver,
    MarkupLocation,
    MarkupSource,
    MarkupVariant,
    ProductionMarkupSource,
    SidecarMarkupSource,
)

__version__ = "0.1.0"

__all__ = [
    "AttributeSpec",
    "AttributeType",
    "CameraKey",
    "CameraNameParser",
    "CameraResolver",
    "MarkupAttributeSchema",
    "MarkupDocument",
    "MarkupError",
    "MarkupLabService",
    "MarkupLocation",
    "MarkupShape",
    "MarkupSource",
    "MarkupVariant",
    "ProductionMarkupSource",
    "ShapeLabel",
    "ShapePosition",
    "ShapeType",
    "SidecarMarkupSource",
    "__version__",
]
