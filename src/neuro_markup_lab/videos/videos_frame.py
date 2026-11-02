"""
Первый кадр видео в JPEG — подложка для карточки и редактора.

cv2 импортируется лениво: модуль поднимается и без OpenCV, а битое видео не роняет запрос.
"""

__all__ = ['FULL_WIDTH', 'PREVIEW_WIDTH', 'first_frame_jpeg', 'frame_size']

import logging
from pathlib import Path

from .videos_types import VIDEO_EXTENSIONS

# Ширина кадра для карточки списка, px
PREVIEW_WIDTH = 960
# Ширина кадра для редактора, px; больше исходной кадр не растягивается
FULL_WIDTH = 1920
# Качество JPEG карточки и редактора
_PREVIEW_QUALITY = 82
_FULL_QUALITY = 90

_log = logging.getLogger(__name__)


def first_frame_jpeg(video_path: Path, max_width: int = PREVIEW_WIDTH) -> bytes | None:
    """ JPEG первого кадра, уменьшенный до ``max_width``, или ``None``, если кадр не прочитать. """
    path = Path(video_path)
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        return None
    try:
        import cv2
    except ImportError:
        _log.warning('OpenCV is not available, video frames are disabled')
        return None
    capture = cv2.VideoCapture(str(path))
    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        height, width = frame.shape[:2]
        if max_width and width > max_width:
            frame = cv2.resize(frame, (max_width, max(1, int(height * max_width / width))),
                               interpolation=cv2.INTER_AREA)
        quality = _FULL_QUALITY if max_width > PREVIEW_WIDTH else _PREVIEW_QUALITY
        ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes() if ok else None
    except cv2.error as exc:
        _log.warning("Cannot read first frame of '%s': %s", path, exc)
        return None
    finally:
        capture.release()


def frame_size(video_path: Path) -> tuple[int, int] | None:
    """
        Исходный размер кадра ``(ширина, высота)`` из заголовка видео или ``None``.
        Нужен, когда в JSON нет imageWidth/imageHeight: координаты фигур — в пикселях исходного кадра.
    """
    path = Path(video_path)
    if not path.is_file():
        return None
    try:
        import cv2
    except ImportError:
        return None
    capture = cv2.VideoCapture(str(path))
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (width, height) if width > 0 and height > 0 else None
    finally:
        capture.release()
