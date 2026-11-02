"""
Системное окно выбора каталога или JSON-файла на компьютере сервера.

Окно tkinter открывается в отдельном процессе: tkinter должен работать в главном потоке своего
процесса, а веб-сервер занят своими потоками. Путь передаётся в UTF-8, чтобы в Windows не терялись
русские буквы.
"""

__all__ = ['PathPickerError', 'pick_path']

import json
import subprocess
import sys

from .web_path_picker_error import PathPickerError
from .web_types import PickKind

# Сколько ждать выбора пользователем, с
_PICK_TIMEOUT_S = 600
# Заголовки окна
_TITLES: dict[PickKind, str] = {PickKind.DIR: 'Выберите каталог', PickKind.JSON: 'Выберите JSON разметки'}

_SCRIPT = r"""
import json, sys, tkinter as tk
from tkinter import filedialog
args = json.loads(sys.argv[1])
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
common = {"initialdir": args["initial"] or None, "title": args["title"]}
if args["kind"] == "dir":
    path = filedialog.askdirectory(mustexist=True, **common)
else:
    path = filedialog.askopenfilename(filetypes=[("Разметка LabelMe", "*.json"), ("Все файлы", "*.*")], **common)
root.destroy()
sys.stdout.buffer.write((path or "").encode("utf-8"))
"""


def pick_path(kind: PickKind, initial: str) -> str | None:
    """ Каталог или файл, выбранный пользователем, или ``None``, если выбор отменён. """
    args = json.dumps({'kind': kind.value, 'initial': initial, 'title': _TITLES[kind]}, ensure_ascii=False)
    try:
        result = subprocess.run([sys.executable, '-c', _SCRIPT, args], capture_output=True,
                                timeout=_PICK_TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PathPickerError(f'Path picker failed: {exc}') from exc
    if result.returncode != 0:
        detail = result.stderr.decode('utf-8', errors='replace').strip().splitlines()
        raise PathPickerError(f'Path picker is not available: {detail[-1] if detail else result.returncode}')
    path = result.stdout.decode('utf-8', errors='replace').strip()
    return path or None
