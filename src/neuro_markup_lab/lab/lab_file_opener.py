"""
Открытие файла в программе по умолчанию на компьютере, где работает сервер страницы.

Страница разметки — локальный инструмент: сервер и браузер на одном компьютере (как и
нативный выбор каталога), поэтому «открыть JSON» — это запуск программы на этом компьютере.
"""

__all__ = ['SystemFileOpener']

import os
import subprocess
import sys
from pathlib import Path

from ..markup import MarkupError

# Команды открытия файла программой по умолчанию вне Windows
_OPEN_COMMANDS: dict[str, str] = {'darwin': 'open'}
_DEFAULT_OPEN_COMMAND = 'xdg-open'


class SystemFileOpener:
    """ Открывает файл программой, связанной с его типом в системе. """

    def open(self, path: Path) -> None:
        """ Запускает программу для ``path`` и не ждёт её завершения. """
        try:
            if sys.platform.startswith('win'):
                os.startfile(str(path))
            else:
                command = _OPEN_COMMANDS.get(sys.platform, _DEFAULT_OPEN_COMMAND)
                subprocess.Popen([command, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise MarkupError(f'Cannot open file {path}: {exc}') from exc
