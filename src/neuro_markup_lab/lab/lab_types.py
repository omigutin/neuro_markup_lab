""" Типы прикладного слоя: элементы списка видео, открытая разметка, запрос и итог сохранения. """

__all__ = ['FileOpener', 'MarkupView', 'SaveRequest', 'SaveResult', 'VideoEntry', 'VideoListing']

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..markup import AttributeSpec, JsonValue, NormalizationReport, ShapeChange
from ..storage import MarkupLocation, MarkupVariant


class FileOpener(Protocol):
    """ Открывает файл для пользователя (подменяется в тестах). """

    def open(self, path: Path) -> None:
        """ Открывает ``path``; ошибка — :class:`MarkupError`. """


def _location_dict(location: MarkupLocation) -> dict[str, JsonValue]:
    return {'variant': location.variant.value, 'name': location.name, 'exists': location.exists,
            'path': str(location.path) if location.path else None, 'reason': location.reason}


@dataclass(frozen=True, slots=True)
class VideoEntry:
    """ Видео в списке страницы и наличие его разметки. """
    path: Path
    relative_dir: str
    factory: str | None
    cam_id: str | None
    sidecar: MarkupLocation
    production: MarkupLocation

    @property
    def default_variant(self) -> MarkupVariant | None:
        """ Что открывать по умолчанию: JSON рядом с видео, если он есть, иначе боевой. """
        if self.sidecar.exists:
            return MarkupVariant.SIDECAR
        if self.production.exists:
            return MarkupVariant.PRODUCTION
        return None

    def as_dict(self) -> dict[str, JsonValue]:
        default = self.default_variant
        return {
            'path': str(self.path), 'name': self.path.name, 'stem': self.path.stem,
            'relative_dir': self.relative_dir, 'factory': self.factory, 'cam_id': self.cam_id,
            'sidecar': _location_dict(self.sidecar), 'production': _location_dict(self.production),
            'default_variant': default.value if default else None,
        }


@dataclass(slots=True)
class VideoListing:
    """ Результат открытия каталога видео. """
    directory: str
    recursive: bool
    jsons_dir: str
    videos: list[VideoEntry] = field(default_factory=list)
    # Ошибка каталога видео (нет каталога и т.п.); пусто — каталог открыт
    error: str = ''
    # Ошибка каталога JSON; пусто — каталог не задан или открыт
    jsons_error: str = ''
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            'directory': self.directory, 'recursive': self.recursive, 'jsons_dir': self.jsons_dir,
            'videos': [v.as_dict() for v in self.videos], 'error': self.error,
            'jsons_error': self.jsons_error, 'warnings': list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class MarkupView:
    """ Открытая разметка видео для карточки и редактора. """
    video: Path
    location: MarkupLocation
    document: dict[str, JsonValue]
    schema: dict[str, JsonValue]
    # Расхождения типов в документе как он есть (до сохранения)
    report: NormalizationReport
    # Исходный размер кадра видео, если известен
    frame_size: tuple[int, int] | None

    def as_dict(self) -> dict[str, JsonValue]:
        shapes = self.document.get('shapes')
        shapes_view: list[JsonValue] = []
        for index, shape in enumerate(shapes if isinstance(shapes, list) else []):
            if not isinstance(shape, dict):
                continue
            shapes_view.append({
                'index': index,
                'points': shape.get('points') or [],
                'shape_type': shape.get('shape_type') or '',
                'attributes': {k: v for k, v in shape.items() if k not in ('points', 'shape_type')},
            })
        width, height = self.frame_size if self.frame_size else (None, None)
        return {
            'video': str(self.video), 'location': _location_dict(self.location),
            'image_width': _opt_int(self.document.get('imageWidth')) or width,
            'image_height': _opt_int(self.document.get('imageHeight')) or height,
            'version': self.document.get('version'),
            'shapes': shapes_view, 'schema': self.schema, 'report': self.report.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class SaveRequest:
    """ Запрос сохранения разметки из редактора. """
    video: Path
    # Что открыто в редакторе (на основе чего правки)
    base_variant: MarkupVariant
    # Куда писать
    target_variant: MarkupVariant
    jsons_dir: str
    # Правки фигур: индекс в shapes[] → правка
    changes: dict[int, ShapeChange]
    # Типы полей документа, заданные в редакторе
    fields: dict[str, AttributeSpec]
    # Только проверить и показать, что будет приведено, без записи
    dry_run: bool
    # Пользователь подтвердил перезапись боевого JSON
    confirm_production: bool


@dataclass(frozen=True, slots=True)
class SaveResult:
    """ Итог сохранения (или проверки перед ним). """
    saved: bool
    target: MarkupLocation
    report: NormalizationReport

    def as_dict(self) -> dict[str, JsonValue]:
        return {'saved': self.saved, 'target': _location_dict(self.target), 'report': self.report.as_dict()}


def _opt_int(value: JsonValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
