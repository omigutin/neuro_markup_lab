""" Типы пакета storage: вариант разметки, её расположение для видео, подбор ключа боевой разметки. """

__all__ = [
    'BACKUP_SUFFIX', 'SIDECAR_SUFFIX', 'VERSIONS_DIR_SUFFIX', 'KeyMatch', 'MarkupKeyResolver', 'MarkupLocation',
    'MarkupVariant', 'MarkupVersion', 'SaveMode', 'VersionHistory', 'VersionOrigin',
]

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias

from ..markup import JsonValue

# Суффикс JSON рядом с видео: ``<stem>.markup.json``
SIDECAR_SUFFIX = '.markup.json'
# Суффикс папки версий разметки рядом с видео: ``<папка видео>/<stem>_jsons/``
VERSIONS_DIR_SUFFIX = '_jsons'
# Суффикс копии боевого JSON перед перезаписью: ``<ключ>.json.bak``
BACKUP_SUFFIX = '.bak'


class MarkupVariant(str, Enum):
    """ Вариант разметки видео. Значение стабильно — уходит в UI и в запросы. """
    SIDECAR = 'sidecar'          # JSON рядом с видео, свой у каждого видео
    PRODUCTION = 'production'    # боевой JSON в каталоге боевых JSON


@dataclass(frozen=True, slots=True)
class MarkupLocation:
    """ Где лежит разметка варианта для видео и есть ли она. """
    variant: MarkupVariant
    # Путь файла; ``None`` — адрес не определить (нет каталога JSON, файл не подобран)
    path: Path | None
    # Файл существует
    exists: bool
    # Почему адрес не определён (для подсказки в UI); пусто, если путь есть
    reason: str = ''
    # Ключ боевой разметки (имя файла без .json); для разметки рядом с видео — пусто
    key: str = ''
    # Боевая разметка выбрана пользователем вручную, а не подобрана
    manual: bool = False

    @property
    def name(self) -> str:
        """ Имя файла разметки или пустая строка. """
        return self.path.name if self.path else ''


@dataclass(frozen=True, slots=True)
class KeyMatch:
    """ Итог подбора ключа боевой разметки по каталогу. """
    # Выбранный ключ; ``None`` — не подобран
    key: str | None
    # Равные лучшие кандидаты, если выбрать не удалось (для подсказки)
    candidates: tuple[str, ...] = ()


# Ключ боевой разметки видео от приложения-хозяина; ``None`` — подобрать по каталогу
MarkupKeyResolver: TypeAlias = Callable[[Path], str | None]


class SaveMode(str, Enum):
    """ Как сохранить разметку рядом с видео. Значение стабильно — приходит из запроса. """
    NEW_VERSION = 'new'          # новой версией; она становится текущей
    OVERWRITE = 'overwrite'      # поверх версии, открытой в редакторе; она становится текущей


class VersionOrigin(str, Enum):
    """ Откуда взялась версия. Значение стабильно — хранится в versions.json. """
    INITIAL = 'initial'          # файл рядом с видео, который был до истории версий
    EXTERNAL = 'external'        # файл изменён не через редактор (сохранён перед записью, чтобы не потерять)
    EDITOR = 'editor'            # сохранена из редактора
    SYNC = 'sync'                # записана синхронизацией с боевой (приложением-хозяином)


@dataclass(slots=True)
class MarkupVersion:
    """ Версия разметки рядом с видео (запись versions.json). """
    # Номер версии: растёт, не переиспользуется
    number: int
    # Имя файла версии в папке версий
    file: str
    # Когда создана и когда последний раз перезаписана (ISO 8601)
    created: str
    updated: str
    # Хэш содержимого файла версии
    hash: str
    # Откуда взялась
    origin: VersionOrigin
    # Номер версии, из которой сделана правка; ``None`` — не из версии
    based_on: int | None = None
    # Какая разметка была открыта в редакторе при сохранении (``sidecar``/``production``); пусто — неизвестно
    source: str = ''
    # Комментарий пользователя
    comment: str = ''
    # Закреплена пользователем (отметка, чтобы быстро найти)
    pinned: bool = False

    def as_dict(self) -> dict[str, JsonValue]:
        return {'number': self.number, 'file': self.file, 'created': self.created, 'updated': self.updated,
                'hash': self.hash, 'origin': self.origin.value, 'based_on': self.based_on, 'source': self.source,
                'comment': self.comment, 'pinned': self.pinned}


@dataclass(slots=True)
class VersionHistory:
    """ Версии разметки видео и текущая (ей равен файл рядом с видео). """
    versions: list[MarkupVersion]
    # Номер текущей версии; ``None`` — версий нет
    current: int | None = None

    def get(self, number: int) -> MarkupVersion | None:
        return next((v for v in self.versions if v.number == number), None)

    @property
    def current_version(self) -> MarkupVersion | None:
        return self.get(self.current) if self.current is not None else None

    def as_dict(self) -> dict[str, JsonValue]:
        return {'current': self.current, 'versions': [v.as_dict() for v in self.versions]}
