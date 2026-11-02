"""
Системное окно выбора каталога на компьютере сервера.

Окно tkinter открывается в отдельном процессе: tkinter должен работать в главном потоке своего
процесса, а веб-сервер занят своими потоками. Путь передаётся в UTF-8, чтобы в Windows не терялись
русские буквы.
"""

__all__ = ['FolderPickerError', 'pick_folder']

import json
import subprocess
import sys

from .web_folder_picker_error import FolderPickerError

# Сколько ждать выбора каталога пользователем, с
_PICK_TIMEOUT_S = 600

_SCRIPT = r"""
import json, sys, tkinter as tk
from tkinter import filedialog
args = json.loads(sys.argv[1])
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askdirectory(initialdir=args["initial"] or None, title=args["title"], mustexist=True)
root.destroy()
sys.stdout.buffer.write((path or "").encode("utf-8"))
"""

# Заголовок окна выбора каталога
_TITLE = 'Выберите каталог'


def pick_folder(initial: str) -> str | None:
    """ Каталог, выбранный пользователем, или ``None``, если выбор отменён. """
    args = json.dumps({'initial': initial, 'title': _TITLE}, ensure_ascii=False)
    try:
        result = subprocess.run([sys.executable, '-c', _SCRIPT, args], capture_output=True,
                                timeout=_PICK_TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FolderPickerError(f'Folder picker failed: {exc}') from exc
    if result.returncode != 0:
        detail = result.stderr.decode('utf-8', errors='replace').strip().splitlines()
        raise FolderPickerError(f'Folder picker is not available: {detail[-1] if detail else result.returncode}')
    path = result.stdout.decode('utf-8', errors='replace').strip()
    return path or None
