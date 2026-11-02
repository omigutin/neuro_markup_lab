"""
Подбор боевой разметки видео по каталогу JSON.

Ключ разметки — имя файла каталога без ``.json`` (``norebo_cam25``). Ключ и путь к видео делятся
на блоки по разделителям ``/ \\ { } - _ . пробел``; регистр не важен. Файл подходит видео, если
каждый блок ключа есть среди блоков пути: сначала ищется в имени видео, затем в папках — от
ближайшей к файлу. Из подходящих выбирается файл, у которого:

1. больше блоков нашлось в имени видео;
2. больше блоков всего (ключ точнее);
3. остальные блоки нашлись в папках ближе к видео;
4. есть блок с производством видео (если хозяин передал список производств).

Равные лучшие кандидаты — разметка не подобрана: выбирать вручную.
"""

__all__ = ['find_factory', 'match_markup_key', 'split_blocks']

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from .storage_types import KeyMatch

# Разделители блоков пути и имени файла
_BLOCK_SPLIT = re.compile(r'[\\/{}\-_. ]+')


def split_blocks(text: str) -> list[str]:
    """ Блоки строки в нижнем регистре, без пустых. """
    return [b for b in _BLOCK_SPLIT.split(text.lower()) if b]


def _video_blocks(video_path: Path) -> tuple[set[str], list[set[str]]]:
    """ Блоки имени видео и блоки папок — от ближайшей к файлу. """
    path = Path(video_path)
    name = set(split_blocks(path.stem))
    folders = [set(split_blocks(part)) for part in reversed(path.parent.parts)]
    return name, folders


def find_factory(video_path: Path, factories: Iterable[str]) -> str | None:
    """ Производство видео из списка: сначала в имени видео, затем в папках от ближайшей. """
    known = {f.lower(): f for f in factories if f}
    if not known:
        return None
    name, folders = _video_blocks(video_path)
    for blocks in (name, *folders):
        found = sorted(block for block in blocks if block in known)
        if found:
            return known[found[0]]
    return None


def _score(key: str, name: set[str], folders: Sequence[set[str]],
           factory: str | None) -> tuple[int, int, int, int] | None:
    """ Оценка ключа (больше — лучше) или ``None``, если ключ видео не подходит. """
    blocks = split_blocks(key)
    if not blocks:
        return None
    in_name, depth_sum = 0, 0
    for block in blocks:
        if block in name:
            in_name += 1
            continue
        depth = next((i for i, folder in enumerate(folders, start=1) if block in folder), None)
        if depth is None:
            return None
        depth_sum += depth
    has_factory = int(factory is not None and factory.lower() in blocks)
    return in_name, len(blocks), -depth_sum, has_factory


def match_markup_key(video_path: Path, keys: Iterable[str], factories: Iterable[str] = ()) -> KeyMatch:
    """ Ключ боевой разметки видео среди ``keys`` по правилам модуля. """
    name, folders = _video_blocks(video_path)
    factory = find_factory(video_path, factories)
    scored: list[tuple[tuple[int, int, int, int], str]] = []
    for key in keys:
        score = _score(key, name, folders, factory)
        if score is not None:
            scored.append((score, key))
    if not scored:
        return KeyMatch(None)
    best = max(score for score, _key in scored)
    leaders = sorted(key for score, key in scored if score == best)
    if len(leaders) > 1:
        return KeyMatch(None, tuple(leaders))
    return KeyMatch(leaders[0])
