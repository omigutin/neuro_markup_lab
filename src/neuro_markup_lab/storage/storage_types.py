""" Типы пакета storage: вариант разметки, её расположение для видео, камера видео. """

__all__ = ['SIDECAR_SUFFIX', 'CameraKey', 'CameraResolver', 'MarkupLocation', 'MarkupVariant']

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias

# Суффикс JSON рядом с видео: ``<stem>.markup.json``
SIDECAR_SUFFIX = '.markup.json'


class MarkupVariant(str, Enum):
    """ Вариант разметки видео. Значение стабильно — уходит в UI и в запросы. """
    SIDECAR = 'sidecar'          # JSON рядом с видео, свой у каждого видео
    PRODUCTION = 'production'    # боевой JSON камеры в каталоге JSON производства


@dataclass(frozen=True, slots=True)
class MarkupLocation:
    """ Где лежит разметка варианта для видео и есть ли она. """
    variant: MarkupVariant
    # Путь файла; ``None`` — адрес не определить (нет каталога JSON или камеры в имени видео)
    path: Path | None
    # Файл существует
    exists: bool
    # Почему адрес не определён (для подсказки в UI); пусто, если путь есть
    reason: str = ''

    @property
    def name(self) -> str:
        """ Имя файла разметки или пустая строка. """
        return self.path.name if self.path else ''


@dataclass(frozen=True, slots=True)
class CameraKey:
    """ Камера, снявшая видео: по ней находится боевая разметка ``<factory>_cam<cam_id>.json``. """
    # Имя фабрики
    factory: str
    # Номер камеры (как в имени файла)
    cam_id: str


# Камера по пути видео; ``None`` — камеру не определить, боевая разметка недоступна
CameraResolver: TypeAlias = Callable[[Path], CameraKey | None]
