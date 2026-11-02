""" Отдельный запуск редактора: свободный порт, сервер, браузер. """

__all__ = ['find_port', 'run']

import json
import socket
import threading
import urllib.request
import webbrowser

from .web_app import create_app
from .web_types import APP_ID, DEFAULT_PORT

# Сколько портов подряд пробовать, если нужный занят
_PORT_ATTEMPTS = 20
# Сколько ждать ответа уже запущенного редактора, с
_PING_TIMEOUT_S = 1.5
# Через сколько открыть браузер после старта сервера, с
_BROWSER_DELAY_S = 1.0


def _port_free(host: str, port: int) -> bool:
    """ Можно ли занять порт. """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _is_markup_lab(host: str, port: int) -> bool:
    """ Работает ли на порту уже запущенный редактор разметки. """
    try:
        with urllib.request.urlopen(f'http://{host}:{port}/api/ping', timeout=_PING_TIMEOUT_S) as response:
            return bool(json.loads(response.read().decode('utf-8')).get('app') == APP_ID)
    except (OSError, ValueError):
        return False


def find_port(host: str, port: int) -> tuple[int, bool]:
    """
        Порт для запуска: ``(порт, уже_запущен)``. Если на порту уже работает редактор — его порт и ``True``;
        если порт занят другой программой — следующий свободный.
    """
    for candidate in range(port, port + _PORT_ATTEMPTS):
        if _port_free(host, candidate):
            return candidate, False
        if _is_markup_lab(host, candidate):
            return candidate, True
    raise OSError(f'No free port in range {port}-{port + _PORT_ATTEMPTS - 1}')


def run(host: str = '127.0.0.1', port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    """
        Запускает редактор со своей страницей. Боевая разметка видео подбирается по файлам каталога JSON.
        Если редактор уже запущен — открывает его в браузере; если порт занят другой программой — берёт следующий.
    """
    import uvicorn

    free_port, running = find_port(host, port)
    url = f'http://{host}:{free_port}/'
    if running:
        print(f'Редактор разметки уже запущен: {url} — открываю его в браузере.')
        if open_browser:
            webbrowser.open(url)
        return
    if free_port != port:
        print(f'Порт {port} занят другой программой, использую {free_port}.')
    app = create_app()
    print(f'Редактор разметки: {url} (остановить — Ctrl+C)')
    if open_browser:
        threading.Timer(_BROWSER_DELAY_S, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=free_port, log_level='warning')
