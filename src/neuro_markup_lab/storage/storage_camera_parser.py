"""
Камера видео по имени и пути файла.

Путь делится на блоки по разделителям ``/ \\ { } - _ . пробел``. Номер камеры — блок ``cam<N>``
в имени файла. Фабрика — блок пути из списка известных фабрик (ближайший к имени файла), а если
список не задан — блок имени файла прямо перед ``cam<N>``: ``plant_cam5_x.avi`` → ``plant``, ``5``.
"""

__all__ = ['CameraNameParser']

import re
from collections.abc import Iterable
from pathlib import Path

from .storage_types import CameraKey

# Разделители блоков пути и имени файла
_BLOCK_SPLIT = re.compile(r'[\\/{}\-_. ]+')
# Блок номера камеры
_CAM_BLOCK = re.compile(r'^cam(\d{1,3})$', re.IGNORECASE)


class CameraNameParser:
    """ Определяет камеру видео по имени файла и, если задан список фабрик, по пути. """

    def __init__(self, factories: Iterable[str] = ()) -> None:
        # Известные фабрики в нижнем регистре; пусто — фабрика берётся из имени файла перед cam<N>
        self._factories: frozenset[str] = frozenset(f.lower() for f in factories if f)

    def __call__(self, video_path: Path) -> CameraKey | None:
        name_blocks = [b for b in _BLOCK_SPLIT.split(Path(video_path).stem) if b]
        for index, block in enumerate(name_blocks):
            match = _CAM_BLOCK.match(block)
            if match is None:
                continue
            factory = self._known_factory(video_path) if self._factories else self._factory_before(name_blocks, index)
            return CameraKey(factory, match.group(1)) if factory else None
        return None

    def _known_factory(self, video_path: Path) -> str | None:
        """ Ближайший к имени файла блок пути, совпадающий с известной фабрикой. """
        blocks = [b.lower() for b in _BLOCK_SPLIT.split(str(video_path)) if b]
        return next((b for b in reversed(blocks) if b in self._factories), None)

    @staticmethod
    def _factory_before(name_blocks: list[str], cam_index: int) -> str | None:
        """ Блок имени файла перед ``cam<N>``. """
        return name_blocks[cam_index - 1].lower() if cam_index > 0 else None
