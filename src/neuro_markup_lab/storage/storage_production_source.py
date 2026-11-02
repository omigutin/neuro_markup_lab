"""
Боевая разметка видео: ``<каталог JSON>/<ключ>.json``.

Каталог JSON — плоский. Ключ разметки видео выбирается так: ключ, выбранный пользователем вручную;
иначе ключ от приложения-хозяина; иначе подбор по файлам каталога (:func:`match_markup_key`).
"""

__all__ = ['ProductionMarkupSource', 'check_key']

from collections.abc import Sequence
from pathlib import Path

from ..markup import JsonValue, MarkupError
from .storage_json_file import write_json_text
from .storage_key_matcher import match_markup_key
from .storage_source import MarkupSource
from .storage_types import BACKUP_SUFFIX, SIDECAR_SUFFIX, MarkupKeyResolver, MarkupLocation, MarkupVariant

# Расширение файлов боевой разметки
_JSON_SUFFIX = '.json'
# Символы, которых не может быть в ключе: ключ — имя файла, а не путь
_KEY_FORBIDDEN = ('/', '\\', '\0')


def check_key(key: str) -> str:
    """ Ключ — имя файла без каталога и без ``.json``; путь в ключе не допускается. """
    if not key or key in ('.', '..') or any(ch in key for ch in _KEY_FORBIDDEN):
        raise MarkupError(f'Invalid production markup key {key!r}')
    return key


class ProductionMarkupSource(MarkupSource):
    """ Источник боевых JSON в каталоге. Создаётся на запрос: список файлов каталога читается один раз. """

    def __init__(self, jsons_dir: Path | None, key_resolver: MarkupKeyResolver | None = None,
                 factories: Sequence[str] = (), manual_key: str | None = None) -> None:
        # Каталог боевых JSON; ``None`` — не задан, боевая разметка недоступна
        self._jsons_dir: Path | None = Path(jsons_dir) if jsons_dir else None
        # Ключ разметки видео от приложения-хозяина
        self._key_resolver = key_resolver
        # Известные производства: помогают выбрать между равными кандидатами
        self._factories: tuple[str, ...] = tuple(factories)
        # Ключ, выбранный пользователем для этого видео
        self._manual_key: str | None = check_key(manual_key) if manual_key else None
        # Ключи файлов каталога (читаются при первом подборе)
        self._catalog: tuple[str, ...] | None = None

    @property
    def variant(self) -> MarkupVariant:
        return MarkupVariant.PRODUCTION

    def locate(self, video_path: Path) -> MarkupLocation:
        if self._jsons_dir is None:
            return MarkupLocation(self.variant, None, False, 'Каталог JSON не задан')
        if self._manual_key:
            return self._location(self._jsons_dir, self._manual_key, manual=True)
        key = self._key_resolver(video_path) if self._key_resolver else None
        if key:
            return self._location(self._jsons_dir, check_key(key))
        match = match_markup_key(video_path, self.catalog_keys(), self._factories)
        if match.key:
            return self._location(self._jsons_dir, match.key)
        if match.candidates:
            names = ', '.join(f'{k}{_JSON_SUFFIX}' for k in match.candidates)
            return MarkupLocation(self.variant, None, False, f'Подходят несколько файлов: {names} — выберите вручную')
        return MarkupLocation(self.variant, None, False, 'Подходящий файл в каталоге не найден — выберите вручную')

    def save(self, video_path: Path, document: dict[str, JsonValue]) -> Path:
        """ Перезаписывает боевой JSON; прежнее содержимое — в ``<ключ>.json.bak`` (одна копия). """
        location = self.locate(video_path)
        if location.path is not None and location.path.is_file():
            backup = location.path.with_name(location.path.name + BACKUP_SUFFIX)
            try:
                text = location.path.read_text(encoding='utf-8')
            except OSError as exc:
                raise MarkupError(f'Cannot read markup file {location.path}: {exc}') from exc
            write_json_text(backup, text)
        return super().save(video_path, document)

    def catalog_keys(self) -> tuple[str, ...]:
        """ Ключи боевых JSON каталога: файлы ``*.json`` без скрытых и без разметки рядом с видео. """
        if self._catalog is None:
            self._catalog = tuple(sorted(
                p.name[:-len(_JSON_SUFFIX)] for p in self._list_dir()
                if p.is_file() and p.name.lower().endswith(_JSON_SUFFIX) and not p.name.startswith('.')
                and not p.name.lower().endswith(SIDECAR_SUFFIX)))
        return self._catalog

    def key_of(self, path: Path) -> str:
        """ Ключ файла, выбранного пользователем: файл должен лежать в каталоге боевых JSON. """
        if self._jsons_dir is None:
            raise MarkupError('Production markup directory is not set')
        path = Path(path)
        if path.suffix.lower() != _JSON_SUFFIX:
            raise MarkupError(f'Markup file must be a .json file: {path}')
        if path.parent.resolve() != self._jsons_dir.resolve():
            raise MarkupError(f'Markup file must be in the production markup directory {self._jsons_dir}: {path}')
        return path.stem

    def _list_dir(self) -> list[Path]:
        if self._jsons_dir is None:
            return []
        try:
            return list(self._jsons_dir.iterdir())
        except OSError:
            return []

    def _location(self, jsons_dir: Path, key: str, manual: bool = False) -> MarkupLocation:
        path = jsons_dir / f'{key}{_JSON_SUFFIX}'
        return MarkupLocation(self.variant, path, path.is_file(), key=key, manual=manual)
