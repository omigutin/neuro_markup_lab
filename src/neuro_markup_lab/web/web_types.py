""" Типы web-слоя NeuroMarkupLab. """

__all__ = ['NAV_KEY', 'PAGE_ROUTE', 'STATIC_PREFIX', 'NavRenderer', 'NeuroMarkupLabWebDependencies']

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from ..lab import MarkupLabService

# Отрисовка общей навигации хоста: (ключ активного раздела, пользователь) → HTML
NavRenderer: TypeAlias = Callable[[str, str], str]

# Адрес страницы разметки
PAGE_ROUTE = '/neuro-markup-lab'
# Префикс статики страницы
STATIC_PREFIX = '/neuro-markup-lab-static'
# Ключ раздела в навигации хоста
NAV_KEY = 'markup'


@dataclass(frozen=True, slots=True)
class NeuroMarkupLabWebDependencies:
    """ Зависимости маршрутов NeuroMarkupLab (лежат в ``app.state.nml_web_deps``). """
    service: MarkupLabService
