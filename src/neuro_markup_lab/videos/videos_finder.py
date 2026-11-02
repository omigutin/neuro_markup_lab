""" Поиск видеофайлов в каталоге. """

__all__ = ['VideoFinder']

import os
from pathlib import Path

from .videos_types import IGNORED_DIR_NAMES, VIDEO_EXTENSIONS, VideoFile


class VideoFinder:
    """
        Ищет видео в каталоге, при ``recursive`` — и в подкаталогах (кроме служебных и скрытых).
        Одинаковые имена в разных подкаталогах допустимы: разметка лежит рядом с каждым видео.
    """

    def find(self, root: Path, recursive: bool, warnings: list[str]) -> list[VideoFile]:
        """
            Видео каталога ``root``, отсортированные по подкаталогу, затем по имени (без учёта регистра):
            видео одного подкаталога идут подряд.
            Недоступные подкаталоги пропускаются с записью в ``warnings``.
        """
        root = Path(root)
        if not recursive:
            files = [p for p in root.iterdir() if _is_video(p) and p.is_file()]
        else:
            files = self._walk(root, warnings)
        videos = [VideoFile(path=p, relative_dir=_relative_dir(p, root)) for p in files]
        videos.sort(key=lambda v: (v.relative_dir.lower(), v.path.name.lower()))
        return videos

    @staticmethod
    def _walk(root: Path, warnings: list[str]) -> list[Path]:
        def on_error(exc: OSError) -> None:
            warnings.append(f'Нет доступа к каталогу: {exc.filename}')

        files: list[Path] = []
        for current, dirnames, filenames in os.walk(root, onerror=on_error):
            dirnames[:] = sorted((d for d in dirnames if d not in IGNORED_DIR_NAMES and not d.startswith('.')),
                                 key=str.lower)
            files.extend(Path(current) / name for name in filenames if _is_video(Path(name)))
        return files


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _relative_dir(path: Path, root: Path) -> str:
    parent = path.parent.relative_to(root)
    return '' if str(parent) == '.' else parent.as_posix()
