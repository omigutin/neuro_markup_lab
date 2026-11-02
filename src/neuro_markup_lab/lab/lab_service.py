"""
Сервис редактора разметки: список видео каталога, открытие и сохранение разметки.

Источники разметки создаются на каждый запрос: каталог боевых JSON выбирает пользователь
на странице, глобального состояния нет.
"""

__all__ = ['MarkupLabService']

import copy
from pathlib import Path

from ..markup import JsonValue, MarkupAttributeSchema, MarkupChangeApplier, MarkupError, MarkupNormalizer
from ..storage import (
    MarkupSource,
    MarkupVariant,
    MarkupVersion,
    ProductionMarkupSource,
    SaveMode,
    SidecarMarkupSource,
    VersionHistory,
    VersionStore,
    file_hash,
    find_factory,
)
from ..videos import VIDEO_EXTENSIONS, VideoFinder, frame_size
from .lab_conflict_error import MarkupConflictError
from .lab_file_opener import SystemFileOpener
from .lab_host import MarkupLabHost
from .lab_types import FileOpener, MarkupView, SaveRequest, SaveResult, VideoEntry, VideoListing


class MarkupLabService:
    """ Операции над видео и их разметкой: список, открытие, сохранение. """

    def __init__(self, finder: VideoFinder | None = None, opener: FileOpener | None = None,
                 host: MarkupLabHost | None = None) -> None:
        self._finder = finder or VideoFinder()
        self._opener: FileOpener = opener or SystemFileOpener()
        # Данные приложения-хозяина: ключ боевой разметки, производства
        self._host: MarkupLabHost = host or MarkupLabHost()

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
        factories = tuple(self._host.factories())
        sources = self._sources(jsons_path, factories=factories)
        for file in files:
            listing.videos.append(self._entry(file.path, file.relative_dir, sources, factories))
        return listing

    def video_entry(self, video: str, jsons_dir: str, production_key: str | None = None,
                    production_path: str | None = None) -> VideoEntry:
        """
            Одно видео и где лежит его разметка. ``production_key`` — боевая разметка, выбранная вручную;
            ``production_path`` — выбранный файл (должен лежать в каталоге боевых JSON).
        """
        video_path = _video_path(video)
        jsons_path, jsons_error = _resolve_jsons_dir(jsons_dir)
        if production_path:
            if jsons_path is None:
                raise MarkupError(f'Production markup directory is not available: {jsons_error or "not set"}')
            production_key = ProductionMarkupSource(jsons_path).key_of(Path(production_path))
        factories = tuple(self._host.factories())
        sources = self._sources(jsons_path, production_key, factories)
        return self._entry(video_path, '', sources, factories)

    def open(self, video: str, variant: MarkupVariant, jsons_dir: str,
             production_key: str | None = None, version: int | None = None) -> MarkupView:
        """
            Разметка ``variant`` для видео и расхождения типов в ней. ``version`` — версия разметки рядом
            с видео вместо файла. Нет разметки — :class:`MarkupError`.
        """
        video_path = _video_path(video)
        jsons_path, _error = _resolve_jsons_dir(jsons_dir)
        source = self._sources(jsons_path, production_key)[variant]
        location = source.locate(video_path)
        current, count = None, 0
        if variant == MarkupVariant.SIDECAR:
            store = VersionStore(video_path)
            history = store.history()
            count = len(history.versions)
            current = history.current if store.working_matches_current(history) else None
        if version is not None:
            if variant != MarkupVariant.SIDECAR:
                raise MarkupError('Only markup beside the video has versions')
            document = store.load(version)
        elif not location.exists:
            raise MarkupError(f'Markup {variant.value} not found for video {video_path}')
        else:
            document = source.load(video_path)
        shapes = document.get('shapes')
        schema = MarkupAttributeSchema.for_shapes(_dict_shapes(shapes))
        # Отчёт строится на копии: показываем, что изменится при сохранении, не меняя документ
        report = MarkupNormalizer(schema).normalize(copy.deepcopy(document))
        return MarkupView(video=video_path, location=location, document=document, schema=schema.as_dict(),
                          report=report, frame_size=frame_size(video_path),
                          file_hash=file_hash(location.path) if location.path else None,
                          markup_version=version if version is not None else current, current_version=current,
                          versions_count=count)

    def open_file(self, video: str, variant: MarkupVariant, jsons_dir: str,
                  production_key: str | None = None, version: int | None = None) -> Path:
        """
            Открывает файл разметки видео в программе по умолчанию: файл варианта или, для разметки рядом
            с видео, файл версии ``version``. Открывается только путь, вычисленный для этого видео, —
            произвольный путь из запроса не принимается.
        """
        video_path = _video_path(video)
        if version is not None:
            if variant != MarkupVariant.SIDECAR:
                raise MarkupError('Only markup beside the video has versions')
            path = self.version_path(video, version)
            self._opener.open(path)
            return path
        jsons_path, _error = _resolve_jsons_dir(jsons_dir)
        location = self._sources(jsons_path, production_key)[variant].locate(video_path)
        if not location.exists or location.path is None:
            raise MarkupError(f'Markup {variant.value} not found for video {video_path}')
        self._opener.open(location.path)
        return location.path

    def open_video(self, video: str) -> Path:
        """ Открывает видеофайл в программе по умолчанию (для просмотра). Открываются только видеофайлы. """
        video_path = _video_path(video)
        self._opener.open(video_path)
        return video_path

    def save(self, request: SaveRequest) -> SaveResult:
        """
            Применяет правки к разметке ``base_variant``, приводит типы во всём документе и пишет
            в ``target_variant``. С ``dry_run`` — только проверка. Запись есть, только если
            приводимых вручную проблем нет; перезапись боевого JSON — только с подтверждением.
        """
        video_path = _video_path(str(request.video))
        jsons_path, jsons_error = _resolve_jsons_dir(request.jsons_dir)
        sources = self._sources(jsons_path, request.production_key)
        base = sources[request.base_variant]
        if not base.locate(video_path).exists:
            raise MarkupError(f'Markup {request.base_variant.value} not found for video {video_path}')
        target = sources[request.target_variant].locate(video_path)
        if target.path is None:
            raise MarkupError(f'Target markup location is unknown: {jsons_error or target.reason}')

        if request.base_variant == MarkupVariant.SIDECAR and request.base_version is not None:
            document = VersionStore(video_path).load(request.base_version)
        else:
            document = base.load(video_path)
        MarkupChangeApplier().apply(document, request.changes)
        schema = MarkupAttributeSchema.for_shapes(_dict_shapes(document.get('shapes')), request.fields)
        report = MarkupNormalizer(schema).normalize(document)
        if request.dry_run or not report.ok:
            return SaveResult(saved=False, target=target, report=report)
        if request.target_variant == MarkupVariant.PRODUCTION and not request.confirm_production:
            raise MarkupError('Writing production markup requires confirmation')
        if request.expected_hash is not None and not request.force and file_hash(target.path) != request.expected_hash:
            raise MarkupConflictError(f'Markup file was changed after it was opened: {target.path}')
        version: MarkupVersion | None = None
        if request.target_variant == MarkupVariant.SIDECAR:
            # Перезаписывается base_version — и когда правили её саму, и когда в неё пишут правку боевой
            overwrite = request.mode == SaveMode.OVERWRITE
            based_on = request.base_version if request.base_variant == MarkupVariant.SIDECAR or overwrite else None
            version = VersionStore(video_path).save(document, request.mode, based_on,
                                                    request.base_variant.value, request.comment)
        else:
            sources[request.target_variant].save(video_path, document)
        saved = sources[request.target_variant].locate(video_path)
        return SaveResult(saved=True, target=saved, report=report, version=version)

    def versions(self, video: str) -> VersionHistory:
        """ Версии разметки рядом с видео и текущая. """
        return VersionStore(_video_path(video)).history()

    def versions_directory(self, video: str) -> Path:
        """ Папка версий разметки рядом с видео. """
        return VersionStore(_video_path(video)).directory

    def working_matches_current(self, video: str) -> bool:
        """ Файл рядом с видео равен текущей версии (не изменён вне версий). """
        return VersionStore(_video_path(video)).working_matches_current()

    def version_path(self, video: str, number: int) -> Path:
        """ Файл версии ``number`` разметки рядом с видео. Нет версии — :class:`MarkupError`. """
        store = VersionStore(_video_path(video))
        version = store.history().get(number)
        if version is None:
            raise MarkupError(f'Markup version {number} not found')
        return store.directory / version.file

    def make_current_version(self, video: str, number: int) -> MarkupVersion:
        """ Делает версию текущей: файл рядом с видео становится равен ей. """
        return VersionStore(_video_path(video)).make_current(number)

    def update_version(self, video: str, number: int, pinned: bool | None = None,
                       comment: str | None = None) -> MarkupVersion:
        """ Отметка «закреплена» и комментарий версии. """
        return VersionStore(_video_path(video)).update(number, pinned, comment)

    def _entry(self, video_path: Path, relative_dir: str, sources: dict[MarkupVariant, MarkupSource],
               factories: tuple[str, ...]) -> VideoEntry:
        return VideoEntry(
            path=video_path, relative_dir=relative_dir, factory=find_factory(video_path, factories),
            sidecar=sources[MarkupVariant.SIDECAR].locate(video_path),
            production=sources[MarkupVariant.PRODUCTION].locate(video_path),
        )

    def _sources(self, jsons_dir: Path | None, production_key: str | None = None,
                 factories: tuple[str, ...] | None = None) -> dict[MarkupVariant, MarkupSource]:
        known = tuple(self._host.factories()) if factories is None else factories
        return {
            MarkupVariant.SIDECAR: SidecarMarkupSource(),
            MarkupVariant.PRODUCTION: ProductionMarkupSource(jsons_dir, self._host.markup_key, known, production_key),
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
