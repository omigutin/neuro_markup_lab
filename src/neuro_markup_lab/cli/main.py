""" Командная строка: ``nml web`` — запустить редактор разметки со своей страницей. """

__all__ = ['build_parser', 'main']

import argparse
from collections.abc import Sequence

# Порт по умолчанию повторён здесь, чтобы разбор аргументов работал без пакетов из [web]
_DEFAULT_PORT = 8790


def _cmd_web(args: argparse.Namespace) -> int:
    try:
        from ..web import run
    except ImportError as exc:
        print(f"Веб-интерфейс не установлен: pip install 'neuro-markup-lab[web]' ({exc})")
        return 1
    run(host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='nml', description='Редактор разметки зон по кадру видео.')
    sub = parser.add_subparsers(dest='command', required=True)
    web = sub.add_parser('web', help='запустить редактор со своей страницей')
    web.add_argument('--host', default='127.0.0.1', help='адрес сервера')
    web.add_argument('--port', type=int, default=_DEFAULT_PORT, help='порт; занят — берётся следующий свободный')
    web.add_argument('--no-browser', action='store_true', help='не открывать браузер')
    web.set_defaults(func=_cmd_web)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result
