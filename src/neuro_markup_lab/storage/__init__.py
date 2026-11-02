"""
Источники разметки видео.

Источник знает, ГДЕ лежит разметка конкретного видео, и умеет её прочитать и записать.
Сейчас есть два файловых источника — JSON рядом с видео и боевые JSON в каталоге;
другие хранилища (например, база) добавляются новой реализацией :class:`MarkupSource`.
"""

__all__ = [
    'BACKUP_SUFFIX',
    'SIDECAR_SUFFIX',
    'VERSIONS_DIR_SUFFIX',
    'KeyMatch',
    'MarkupKeyResolver',
    'MarkupLocation',
    'MarkupSource',
    'MarkupVariant',
    'MarkupVersion',
    'ProductionMarkupSource',
    'SaveMode',
    'SidecarMarkupSource',
    'VersionHistory',
    'VersionOrigin',
    'VersionStore',
    'dump_json_document',
    'file_hash',
    'find_factory',
    'match_markup_key',
    'read_json_document',
    'split_blocks',
    'text_hash',
    'write_json_document',
    'write_json_text',
]

from .storage_json_file import (
    dump_json_document,
    file_hash,
    read_json_document,
    text_hash,
    write_json_document,
    write_json_text,
)
from .storage_key_matcher import find_factory, match_markup_key, split_blocks
from .storage_production_source import ProductionMarkupSource
from .storage_sidecar_source import SidecarMarkupSource
from .storage_source import MarkupSource
from .storage_types import (
    BACKUP_SUFFIX,
    SIDECAR_SUFFIX,
    VERSIONS_DIR_SUFFIX,
    KeyMatch,
    MarkupKeyResolver,
    MarkupLocation,
    MarkupVariant,
    MarkupVersion,
    SaveMode,
    VersionHistory,
    VersionOrigin,
)
from .storage_version_store import VersionStore
