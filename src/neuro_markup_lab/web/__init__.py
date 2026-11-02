"""
Веб-интерфейс редактора разметки. Импортируется только явно и требует пакетов из ``[web]``.

Встраивание: :func:`mount_app`; отдельное приложение: :func:`create_app`; запуск: :func:`run`.
"""

__all__ = [
    'APP_ID', 'DEFAULT_PORT', 'DEFAULT_PREFIX', 'FolderPicker', 'FolderPickerError', 'NavRenderer',
    'NeuroMarkupLabWebDependencies', 'create_app', 'find_port', 'mount_app', 'pick_folder', 'run',
]

from .web_app import create_app, mount_app
from .web_folder_picker import pick_folder
from .web_folder_picker_error import FolderPickerError
from .web_server import find_port, run
from .web_types import APP_ID, DEFAULT_PORT, DEFAULT_PREFIX, FolderPicker, NavRenderer, NeuroMarkupLabWebDependencies
