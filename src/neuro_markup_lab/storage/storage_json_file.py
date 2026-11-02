""" Чтение и атомарная запись LabelMe JSON. """

__all__ = ['read_json_document', 'write_json_document']

import json
import os
from pathlib import Path

from ..markup import JsonValue, MarkupError

# Отступ как у LabelMe
_JSON_INDENT = 2
# Суффикс временного файла при атомарной записи
_TMP_SUFFIX = '.tmp'


def read_json_document(path: Path) -> dict[str, JsonValue]:
    """ Читает JSON-объект из ``path``. Нет файла, битый JSON или не объект — :class:`MarkupError`. """
    try:
        with Path(path).open('r', encoding='utf-8') as stream:
            document = json.load(stream)
    except FileNotFoundError as exc:
        raise MarkupError(f'Markup file not found: {path}') from exc
    except (OSError, ValueError) as exc:
        raise MarkupError(f'Cannot read markup file {path}: {exc}') from exc
    if not isinstance(document, dict):
        raise MarkupError(f'Markup file {path} is not a JSON object')
    return document


def write_json_document(path: Path, document: dict[str, JsonValue]) -> None:
    """ Атомарно пишет ``document`` в ``path``: сначала во временный файл, затем замена. """
    path = Path(path)
    # ensure_ascii=False — кириллица как есть; порядок ключей сохраняется
    text = json.dumps(document, ensure_ascii=False, indent=_JSON_INDENT)
    tmp = path.with_name(path.name + _TMP_SUFFIX)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)
    except OSError as exc:
        raise MarkupError(f'Cannot write markup file {path}: {exc}') from exc
