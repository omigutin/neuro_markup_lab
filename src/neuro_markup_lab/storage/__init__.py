"""
Источники разметки видео.

Источник знает, ГДЕ лежит разметка конкретного видео, и умеет её прочитать и записать.
Сейчас есть два файловых источника — JSON рядом с видео и боевые JSON в каталоге;
другие хранилища (например, база) добавляются новой реализацией :class:`MarkupSource`.
"""

__all__ = [
    'SIDECAR_SUFFIX',
    'KeyMatch',
    'MarkupKeyResolver',
    'MarkupLocation',
    'MarkupSource',
    'MarkupVariant',
    'ProductionMarkupSource',
    'SidecarMarkupSource',
    'find_factory',
    'match_markup_key',
    'read_json_document',
    'split_blocks',
    'write_json_document',
]

from .storage_json_file import read_json_document, write_json_document
from .storage_key_matcher import find_factory, match_markup_key, split_blocks
from .storage_production_source import ProductionMarkupSource
from .storage_sidecar_source import SidecarMarkupSource
from .storage_source import MarkupSource
from .storage_types import SIDECAR_SUFFIX, KeyMatch, MarkupKeyResolver, MarkupLocation, MarkupVariant
