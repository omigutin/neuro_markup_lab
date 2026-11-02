""" Проверки каркаса пакета. """

import os
import subprocess
import sys

import neuro_markup_lab


def test_version() -> None:
    """ Версия пакета задана. """
    assert neuro_markup_lab.__version__ == "0.1.0"


def test_import_without_web() -> None:
    """ Импорт пакета не подключает веб-часть: библиотекой можно пользоваться без fastapi. """
    code = "import sys, neuro_markup_lab; print('fastapi' in sys.modules)"
    # Дочернему процессу передаётся путь к src из настроек pytest, иначе пакет в нём не найдётся.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env)
    assert result.stdout.strip() == "False"
