"""
Источники разметки видео.

Источник знает, ГДЕ лежит разметка конкретного видео, и умеет её прочитать и записать.
Сейчас есть два файловых источника — JSON рядом с видео и боевые JSON производства;
другие хранилища (например, база) добавляются новой реализацией :class:`MarkupSource`.
"""

__all__ = [
    'SIDECAR_SUFFIX',
    'CameraKey',
    'CameraNameParser',
    'CameraResolver',
    'MarkupLocation',
    'MarkupSource',
    'MarkupVariant',
    'ProductionMarkupSource',
    'SidecarMarkupSource',
    'read_json_document',
    'write_json_document',
]

from .storage_camera_parser import CameraNameParser
from .storage_json_file import read_json_document, write_json_document
from .storage_production_source import ProductionMarkupSource
from .storage_sidecar_source import SidecarMarkupSource
from .storage_source import MarkupSource
from .storage_types import SIDECAR_SUFFIX, CameraKey, CameraResolver, MarkupLocation, MarkupVariant
