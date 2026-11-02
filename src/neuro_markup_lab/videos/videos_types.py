""" Типы пакета videos. """

__all__ = ['IGNORED_DIR_NAMES', 'VIDEO_EXTENSIONS', 'VideoFile']

from dataclasses import dataclass
from pathlib import Path

# Расширения видеофайлов (в нижнем регистре)
VIDEO_EXTENSIONS: frozenset[str] = frozenset({'.mp4', '.avi', '.mov', '.mkv', '.m4v'})

# Подкаталоги, которые не обходятся при поиске: ``runs`` — артефакты прогонов, в том числе
# записанные видео; скрытые каталоги (с точки) пропускаются всегда
IGNORED_DIR_NAMES: frozenset[str] = frozenset({'runs'})


@dataclass(frozen=True, slots=True)
class VideoFile:
    """ Найденный видеофайл. """
    # Полный путь
    path: Path
    # Подкаталог относительно корня поиска ('' — сам корень), разделитель '/'
    relative_dir: str
