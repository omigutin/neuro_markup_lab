""" Чтение и атомарная запись LabelMe JSON. """

__all__ = [
    'dump_json_document', 'file_hash', 'read_json_document', 'text_hash', 'write_json_document', 'write_json_text',
]

import hashlib
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


def dump_json_document(document: dict[str, JsonValue]) -> str:
    """ Текст JSON документа: отступ как у LabelMe, кириллица как есть, порядок ключей сохраняется. """
    return json.dumps(document, ensure_ascii=False, indent=_JSON_INDENT)


def write_json_text(path: Path, text: str) -> None:
    """ Атомарно пишет текст в ``path``: сначала во временный файл, затем замена. """
    path = Path(path)
    tmp = path.with_name(path.name + _TMP_SUFFIX)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, path)
    except OSError as exc:
        raise MarkupError(f'Cannot write markup file {path}: {exc}') from exc


def write_json_document(path: Path, document: dict[str, JsonValue]) -> None:
    """ Атомарно пишет ``document`` в ``path``. """
    write_json_text(path, dump_json_document(document))


def text_hash(text: str) -> str:
    """ Хэш содержимого файла (SHA-256 байтов UTF-8). """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def file_hash(path: Path) -> str | None:
    """ Хэш содержимого файла или ``None``, если файла нет. """
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MarkupError(f'Cannot read markup file {path}: {exc}') from exc
