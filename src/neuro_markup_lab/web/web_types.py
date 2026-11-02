""" Типы веб-слоя: зависимости маршрутов, навигация хозяина, окно выбора каталога, константы. """

__all__ = ['APP_ID', 'DEFAULT_PORT', 'DEFAULT_PREFIX', 'FolderPicker', 'NavRenderer', 'NeuroMarkupLabWebDependencies']

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from ..lab import MarkupLabService

# Имя приложения в ответе ``api/ping``: так запуск узнаёт уже работающий редактор на порту
APP_ID = 'neuro_markup_lab'
# Порт отдельного запуска по умолчанию
DEFAULT_PORT = 8790
# Адрес страницы при встраивании в другое приложение по умолчанию
DEFAULT_PREFIX = '/neuro-markup-lab'

# Навигация приложения-хозяина: готовый HTML над страницей разметки
NavRenderer: TypeAlias = Callable[[], str]
# Окно выбора каталога: начальный каталог → выбранный каталог или ``None`` (отмена)
FolderPicker: TypeAlias = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class NeuroMarkupLabWebDependencies:
    """ Зависимости маршрутов (лежат в ``app.state.nml`` приложения редактора). """
    # Операции над видео и разметкой
    service: MarkupLabService
    # Навигация хозяина над страницей; ``None`` — без навигации
    nav_renderer: NavRenderer | None
    # Окно выбора каталога на компьютере сервера
    folder_picker: FolderPicker
