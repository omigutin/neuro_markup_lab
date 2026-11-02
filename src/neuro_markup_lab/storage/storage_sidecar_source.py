""" Разметка рядом с видео: ``<stem>.markup.json``, своя у каждого видео. """

__all__ = ['SidecarMarkupSource']

from pathlib import Path

from .storage_source import MarkupSource
from .storage_types import SIDECAR_SUFFIX, MarkupLocation, MarkupVariant


class SidecarMarkupSource(MarkupSource):
    """ Источник JSON рядом с видео. """

    @property
    def variant(self) -> MarkupVariant:
        return MarkupVariant.SIDECAR

    def locate(self, video_path: Path) -> MarkupLocation:
        video_path = Path(video_path)
        path = video_path.parent / f'{video_path.stem}{SIDECAR_SUFFIX}'
        return MarkupLocation(self.variant, path, path.is_file())
