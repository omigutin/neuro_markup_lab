""" Источник разметки видео: где лежит, чтение и запись. """

__all__ = ['MarkupSource']

from abc import ABC, abstractmethod
from pathlib import Path

from ..markup import JsonValue, MarkupError
from .storage_json_file import read_json_document, write_json_document
from .storage_types import MarkupLocation, MarkupVariant


class MarkupSource(ABC):
    """
        Базовый файловый источник: наследник решает только, где лежит файл.
        Нефайловое хранилище переопределяет :meth:`load` и :meth:`save`.
    """

    @property
    @abstractmethod
    def variant(self) -> MarkupVariant:
        """ Вариант разметки, за который отвечает источник. """

    @abstractmethod
    def locate(self, video_path: Path) -> MarkupLocation:
        """ Расположение разметки видео. """

    def load(self, video_path: Path) -> dict[str, JsonValue]:
        """ Документ разметки видео. Нет разметки — :class:`MarkupError`. """
        location = self.locate(video_path)
        if location.path is None:
            raise MarkupError(f'Markup location is unknown for video {video_path}')
        return read_json_document(location.path)

    def save(self, video_path: Path, document: dict[str, JsonValue]) -> Path:
        """ Записывает документ разметки видео и возвращает путь записанного файла. """
        location = self.locate(video_path)
        if location.path is None:
            raise MarkupError(f'Markup location is unknown for video {video_path}')
        write_json_document(location.path, document)
        return location.path
