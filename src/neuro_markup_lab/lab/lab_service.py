"""
Сервис редактора разметки: список видео каталога, открытие и сохранение разметки.

Источники разметки создаются на каждый запрос: каталог JSON производства выбирает
пользователь на странице, глобального состояния нет.
"""

__all__ = ['MarkupLabService']

import copy
from pathlib import Path

from ..markup import JsonValue, MarkupAttributeSchema, MarkupChangeApplier, MarkupError, MarkupNormalizer
from ..storage import (
    CameraNameParser,
    CameraResolver,
    MarkupSource,
    MarkupVariant,
    ProductionMarkupSource,
    SidecarMarkupSource,
)
from ..videos import VIDEO_EXTENSIONS, VideoFinder, frame_size
from .lab_file_opener import SystemFileOpener
from .lab_types import FileOpener, MarkupView, SaveRequest, SaveResult, VideoEntry, VideoListing


class MarkupLabService:
    """ Операции страницы разметки над видео и их разметкой. """

    def __init__(self, finder: VideoFinder | None = None, opener: FileOpener | None = None,
                 camera_resolver: CameraResolver | None = None) -> None:
        self._finder = finder or VideoFinder()
        self._opener: FileOpener = opener or SystemFileOpener()
        # Камера по пути видео: по ней находится боевая разметка
        self._camera_resolver: CameraResolver = camera_resolver or CameraNameParser()

    def list_videos(self, directory: str, recursive: bool, jsons_dir: str) -> VideoListing:
        """ Видео каталога ``directory`` с наличием разметки рядом с видео и в каталоге JSON. """
        listing = VideoListing(directory=directory, recursive=recursive, jsons_dir=jsons_dir)
        jsons_path, listing.jsons_error = _resolve_jsons_dir(jsons_dir)
        if not directory:
            listing.error = 'Каталог видео не указан.'
            return listing
        root = Path(directory)
        if not root.is_dir():
            listing.error = 'Каталог видео не найден.'
            return listing
        try:
            files = self._finder.find(root, recursive, listing.warnings)
        except OSError as exc:
            listing.error = f'Каталог видео не прочитать: {exc}'
            return listing
        sources = self._sources(jsons_path)
        for file in files:
            camera = self._camera_resolver(file.path)
            listing.videos.append(VideoEntry(
                path=file.path, relative_dir=file.relative_dir,
                factory=camera.factory if camera else None, cam_id=camera.cam_id if camera else None,
                sidecar=sources[MarkupVariant.SIDECAR].locate(file.path),
                production=sources[MarkupVariant.PRODUCTION].locate(file.path),
            ))
        return listing

    def open(self, video: str, variant: MarkupVariant, jsons_dir: str) -> MarkupView:
        """ Разметка ``variant`` для видео и расхождения типов в ней. Нет разметки — :class:`MarkupError`. """
        video_path = _video_path(video)
        jsons_path, _error = _resolve_jsons_dir(jsons_dir)
        source = self._sources(jsons_path)[variant]
        location = source.locate(video_path)
        if not location.exists:
            raise MarkupError(f'Markup {variant.value} not found for video {video_path}')
        document = source.load(video_path)
        shapes = document.get('shapes')
        schema = MarkupAttributeSchema.for_shapes(_dict_shapes(shapes))
        # Отчёт строится на копии: показываем, что изменится при сохранении, не меняя документ
        report = MarkupNormalizer(schema).normalize(copy.deepcopy(document))
        return MarkupView(video=video_path, location=location, document=document, schema=schema.as_dict(),
                          report=report, frame_size=frame_size(video_path))

    def open_file(self, video: str, variant: MarkupVariant, jsons_dir: str) -> Path:
        """
            Открывает файл разметки видео в программе по умолчанию. Открывается только путь,
            вычисленный источником для этого видео, — произвольный путь из запроса не принимается.
        """
        video_path = _video_path(video)
        jsons_path, _error = _resolve_jsons_dir(jsons_dir)
        location = self._sources(jsons_path)[variant].locate(video_path)
        if not location.exists or location.path is None:
            raise MarkupError(f'Markup {variant.value} not found for video {video_path}')
        self._opener.open(location.path)
        return location.path

    def save(self, request: SaveRequest) -> SaveResult:
        """
            Применяет правки к разметке ``base_variant``, приводит типы во всём документе и пишет
            в ``target_variant``. С ``dry_run`` — только проверка. Запись есть, только если
            приводимых вручную проблем нет; перезапись боевого JSON — только с подтверждением.
        """
        video_path = _video_path(str(request.video))
        jsons_path, jsons_error = _resolve_jsons_dir(request.jsons_dir)
        sources = self._sources(jsons_path)
        base = sources[request.base_variant]
        if not base.locate(video_path).exists:
            raise MarkupError(f'Markup {request.base_variant.value} not found for video {video_path}')
        target = sources[request.target_variant].locate(video_path)
        if target.path is None:
            raise MarkupError(f'Target markup location is unknown: {jsons_error or target.reason}')

        document = base.load(video_path)
        MarkupChangeApplier().apply(document, request.changes)
        schema = MarkupAttributeSchema.for_shapes(_dict_shapes(document.get('shapes')), request.fields)
        report = MarkupNormalizer(schema).normalize(document)
        if request.dry_run or not report.ok:
            return SaveResult(saved=False, target=target, report=report)
        if request.target_variant == MarkupVariant.PRODUCTION and not request.confirm_production:
            raise MarkupError('Writing production markup requires confirmation')
        sources[request.target_variant].save(video_path, document)
        saved = sources[request.target_variant].locate(video_path)
        return SaveResult(saved=True, target=saved, report=report)

    def _sources(self, jsons_dir: Path | None) -> dict[MarkupVariant, MarkupSource]:
        return {
            MarkupVariant.SIDECAR: SidecarMarkupSource(),
            MarkupVariant.PRODUCTION: ProductionMarkupSource(jsons_dir, self._camera_resolver),
        }


def _resolve_jsons_dir(jsons_dir: str) -> tuple[Path | None, str]:
    """ Каталог JSON производства и текст ошибки: не задан — ``(None, '')``, не найден — ошибка. """
    if not jsons_dir:
        return None, ''
    path = Path(jsons_dir)
    if not path.is_dir():
        return None, 'Каталог JSON не найден.'
    return path, ''


def _video_path(video: str) -> Path:
    path = Path(video)
    if not video or not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise MarkupError(f'Video file not found: {video}')
    return path


def _dict_shapes(shapes: object) -> list[dict[str, JsonValue]]:
    return [s for s in shapes if isinstance(s, dict)] if isinstance(shapes, list) else []
