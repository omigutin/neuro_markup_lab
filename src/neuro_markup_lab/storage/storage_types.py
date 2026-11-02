""" Типы пакета storage: вариант разметки, её расположение для видео, подбор ключа боевой разметки. """

__all__ = ['SIDECAR_SUFFIX', 'KeyMatch', 'MarkupKeyResolver', 'MarkupLocation', 'MarkupVariant']

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
