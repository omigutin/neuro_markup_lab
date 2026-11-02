""" Типы веб-слоя: зависимости маршрутов, навигация хозяина, окно выбора пути, константы. """

__all__ = [
    'APP_ID', 'DEFAULT_PORT', 'DEFAULT_PREFIX', 'NavRenderer', 'NeuroMarkupLabWebDependencies', 'PathPicker',
    'PickKind',
]

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from ..lab import MarkupLabService

# Имя приложения в ответе ``api/ping``: так запуск узнаёт уже работающий редактор на порту
APP_ID = 'neuro_markup_lab'
# Порт отдельного запуска по умолчанию
DEFAULT_PORT = 8790
# Адрес страницы при встраивании в другое приложение по умолчанию
DEFAULT_PREFIX = '/neuro-markup-lab'


class PickKind(str, Enum):
    """ Что выбирать в окне выбора. Значение стабильно — приходит из запроса. """
    DIR = 'dir'      # каталог
    JSON = 'json'    # JSON-файл разметки


# Навигация приложения-хозяина: готовый HTML над страницей разметки
NavRenderer: TypeAlias = Callable[[], str]
# Окно выбора: (что выбрать, начальный каталог) → выбранный путь или ``None`` (отмена)
PathPicker: TypeAlias = Callable[[PickKind, str], str | None]


@dataclass(frozen=True, slots=True)
class NeuroMarkupLabWebDependencies:
    """ Зависимости маршрутов (лежат в ``app.state.nml`` приложения редактора). """
    # Операции над видео и разметкой
    service: MarkupLabService
    # Навигация хозяина над страницей; ``None`` — без навигации
    nav_renderer: NavRenderer | None
    # Окно выбора каталога или файла на компьютере сервера
    path_picker: PathPicker
