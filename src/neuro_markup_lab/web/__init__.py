"""
Веб-интерфейс редактора разметки. Импортируется только явно и требует пакетов из ``[web]``.

Встраивание: :func:`mount_app`; отдельное приложение: :func:`create_app`; запуск: :func:`run`.
"""

__all__ = [
    'APP_ID', 'DEFAULT_PORT', 'DEFAULT_PREFIX', 'NavRenderer', 'NeuroMarkupLabWebDependencies', 'PathPicker',
    'PathPickerError', 'PickKind', 'create_app', 'find_port', 'mount_app', 'pick_path', 'run',
]

from .web_app import create_app, mount_app
from .web_path_picker import pick_path
from .web_path_picker_error import PathPickerError
from .web_server import find_port, run
from .web_types import (
    APP_ID,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    NavRenderer,
    NeuroMarkupLabWebDependencies,
    PathPicker,
    PickKind,
)
