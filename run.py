""" Запуск редактора разметки из папки проекта, без установки пакета.

    python run.py                          — открыть редактор в браузере;
    python run.py --port 8791 --no-browser — параметры как у «nml web».
"""

import sys
from pathlib import Path

# Запуск прямо из папки проекта, без установки пакета.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from neuro_markup_lab.cli import main

if __name__ == "__main__":
    sys.exit(main(["web", *sys.argv[1:]]))
