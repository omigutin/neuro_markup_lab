"""
Боевая разметка камеры: ``<каталог JSON производства>/<factory>_cam<cam_id>.json``.

Каталог JSON производства — плоский, все JSON камер лежат в нём без подкаталогов.
Камеру видео определяет :data:`CameraResolver` (по умолчанию — :class:`CameraNameParser`).
"""

__all__ = ['ProductionMarkupSource']

from pathlib import Path

from .storage_camera_parser import CameraNameParser
from .storage_source import MarkupSource
from .storage_types import CameraResolver, MarkupLocation, MarkupVariant


class ProductionMarkupSource(MarkupSource):
    """ Источник боевых JSON камер производства. """

    def __init__(self, jsons_dir: Path | None, camera_resolver: CameraResolver | None = None) -> None:
        # Каталог JSON производства; ``None`` — не задан, боевая разметка недоступна
        self._jsons_dir: Path | None = Path(jsons_dir) if jsons_dir else None
        # Камера по пути видео
        self._camera_resolver: CameraResolver = camera_resolver or CameraNameParser()

    @property
    def variant(self) -> MarkupVariant:
        return MarkupVariant.PRODUCTION

    def locate(self, video_path: Path) -> MarkupLocation:
        if self._jsons_dir is None:
            return MarkupLocation(self.variant, None, False, 'Каталог JSON не задан')
        camera = self._camera_resolver(video_path)
        if camera is None:
            return MarkupLocation(self.variant, None, False, 'Камера не определена по имени видео')
        path = self._jsons_dir / f'{camera.factory}_cam{camera.cam_id}.json'
        return MarkupLocation(self.variant, path, path.is_file())
