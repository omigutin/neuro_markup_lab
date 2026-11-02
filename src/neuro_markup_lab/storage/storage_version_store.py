"""
Версии разметки рядом с видео.

Версии лежат в ``<папка видео>/<имя видео>_jsons/``: файлы ``v<N>_<ГГГГММДД-ЧЧММСС>.json`` и указатель
``versions.json`` (список версий и текущая). Файл рядом с видео ``<имя видео>.markup.json`` всегда равен
текущей версии — его читают все, кто пользуется разметкой. Число версий не ограничено.

Если файл рядом с видео изменён не через редактор (не совпадает с текущей версией), перед любой записью
его содержимое сохраняется отдельной версией: ничего не теряется. Правила — ``docs/markup_versions.md``.
"""

__all__ = ['VersionStore']

import json
from datetime import datetime
from pathlib import Path

from ..markup import JsonValue, MarkupError
from .storage_json_file import dump_json_document, file_hash, read_json_document, text_hash, write_json_text
from .storage_types import SIDECAR_SUFFIX, VERSIONS_DIR_SUFFIX, MarkupVersion, SaveMode, VersionHistory, VersionOrigin

# Имя указателя версий
_INDEX_NAME = 'versions.json'
# Версия формата указателя
_INDEX_FORMAT = 1
# Формат времени в имени файла версии
_FILE_TIME_FORMAT = '%Y%m%d-%H%M%S'


def _now() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


class VersionStore:
    """ Версии разметки одного видео. Создаётся на запрос; состояние — в файлах. """

    def __init__(self, video_path: Path) -> None:
        video_path = Path(video_path)
        # Файл разметки рядом с видео (равен текущей версии)
        self.working_path: Path = video_path.parent / f'{video_path.stem}{SIDECAR_SUFFIX}'
        # Папка версий
        self.directory: Path = video_path.parent / f'{video_path.stem}{VERSIONS_DIR_SUFFIX}'
        self._index_path = self.directory / _INDEX_NAME

    # ---- чтение
    def history(self) -> VersionHistory:
        """ Версии и текущая. Нет папки версий — пустая история. """
        try:
            raw = json.loads(self._index_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return VersionHistory([])
        except (OSError, ValueError) as exc:
            raise MarkupError(f'Cannot read markup versions {self._index_path}: {exc}') from exc
        try:
            versions = [MarkupVersion(
                number=int(v['number']), file=str(v['file']), created=str(v['created']), updated=str(v['updated']),
                hash=str(v['hash']), origin=VersionOrigin(v['origin']), based_on=v.get('based_on'),
                source=str(v.get('source') or ''), comment=str(v.get('comment') or ''), pinned=bool(v.get('pinned')),
            ) for v in raw.get('versions', [])]
            current = raw.get('current')
            return VersionHistory(versions, int(current) if current is not None else None)
        except (KeyError, TypeError, ValueError) as exc:
            raise MarkupError(f'Invalid markup versions file {self._index_path}: {exc}') from exc

    def load(self, number: int) -> dict[str, JsonValue]:
        """ Документ версии ``number``. Нет версии — :class:`MarkupError`. """
        version = self._require(self.history(), number)
        return read_json_document(self.directory / version.file)

    def working_matches_current(self, history: VersionHistory | None = None) -> bool:
        """ Файл рядом с видео равен текущей версии (или нет ни файла, ни версий). """
        history = history or self.history()
        current = history.current_version
        working = file_hash(self.working_path)
        return working == (current.hash if current else None)

    # ---- запись
    def save(self, document: dict[str, JsonValue], mode: SaveMode, base_version: int | None = None,
             source: str = '', comment: str = '', origin: VersionOrigin = VersionOrigin.EDITOR) -> MarkupVersion:
        """
            Сохраняет документ: новой версией (``NEW_VERSION``) или поверх ``base_version`` (``OVERWRITE``).
            Сохранённая версия становится текущей, файл рядом с видео — равен ей. ``origin`` — откуда новая
            версия (``EDITOR`` из редактора, ``SYNC`` — синхронизация приложением-хозяином).
        """
        history = self._capture_working(self.history())
        text = dump_json_document(document)
        now = _now()
        target = history.get(base_version) if mode == SaveMode.OVERWRITE and base_version is not None else None
        if mode == SaveMode.OVERWRITE and target is None:
            raise MarkupError(f'Markup version {base_version} not found for overwrite')
        if target is not None:
            write_json_text(self.directory / target.file, text)
            target.hash, target.updated = text_hash(text), now.isoformat()
            if comment:
                target.comment = comment
            version = target
        else:
            version = self._add(history, text, origin, now, base_version, source, comment)
        history.current = version.number
        write_json_text(self.working_path, text)
        self._write_index(history)
        return version

    def make_current(self, number: int) -> MarkupVersion:
        """ Делает версию текущей: файл рядом с видео становится равен ей. """
        history = self._capture_working(self.history())
        version = self._require(history, number)
        text = (self.directory / version.file).read_text(encoding='utf-8')
        write_json_text(self.working_path, text)
        history.current = number
        self._write_index(history)
        return version

    def update(self, number: int, pinned: bool | None = None, comment: str | None = None) -> MarkupVersion:
        """ Меняет отметку «закреплена» и/или комментарий версии. """
        history = self.history()
        version = self._require(history, number)
        if pinned is not None:
            version.pinned = pinned
        if comment is not None:
            version.comment = comment
        self._write_index(history)
        return version

    # ---- внутреннее
    def _capture_working(self, history: VersionHistory) -> VersionHistory:
        """ Файл рядом с видео не равен текущей версии — сохранить его версией, чтобы не потерять. """
        if not self.working_path.is_file() or self.working_matches_current(history):
            return history
        text = self.working_path.read_text(encoding='utf-8')
        origin = VersionOrigin.EXTERNAL if history.versions else VersionOrigin.INITIAL
        version = self._add(history, text, origin, _now(), None, '', '')
        history.current = version.number
        self._write_index(history)
        return history

    def _add(self, history: VersionHistory, text: str, origin: VersionOrigin, now: datetime,
             based_on: int | None, source: str, comment: str) -> MarkupVersion:
        number = max((v.number for v in history.versions), default=0) + 1
        name = f'v{number}_{now.strftime(_FILE_TIME_FORMAT)}.json'
        write_json_text(self.directory / name, text)
        version = MarkupVersion(number=number, file=name, created=now.isoformat(), updated=now.isoformat(),
                                hash=text_hash(text), origin=origin, based_on=based_on, source=source, comment=comment)
        history.versions.append(version)
        return version

    def _write_index(self, history: VersionHistory) -> None:
        data = {'format': _INDEX_FORMAT, **history.as_dict()}
        write_json_text(self._index_path, json.dumps(data, ensure_ascii=False, indent=2))

    @staticmethod
    def _require(history: VersionHistory, number: int) -> MarkupVersion:
        version = history.get(number)
        if version is None:
            raise MarkupError(f'Markup version {number} not found')
        return version
