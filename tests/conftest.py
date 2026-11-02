""" Общие фикстуры тестов: видео и JSON разметки во временном каталоге. """

import json
from collections.abc import Callable
from pathlib import Path

import pytest

# Имя видео, из которого разбираются фабрика plant и камера 5
VIDEO_NAME = 'plant_cam5_x.avi'
PRODUCTION_NAME = 'plant_cam5.json'


def make_document(shapes: list[dict]) -> dict:
    """ LabelMe JSON с заданными фигурами и типичными полями документа. """
    return {'version': '5.5.0', 'flags': {}, 'shapes': shapes, 'imagePath': 'cam.jpg', 'imageData': None,
            'imageHeight': 1080, 'imageWidth': 1920, 'lineColor': [0, 255, 0, 128]}


def write_json(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


@pytest.fixture
def sample_shapes() -> list[dict]:
    return [
        {'label': 'crop', 'points': [[10, 20], [110, 220]], 'group_id': 2, 'description': None,
         'shape_type': 'rectangle', 'flags': {}, 'mask': None, 'position': 'left', 'wz': '1'},
        {'label': 'input', 'points': [[0, 0], [100, 0], [100, 100]], 'group_id': None, 'description': '',
         'shape_type': 'polygon', 'flags': {}, 'mask': None, 'position': 'right', 'wz': 2, 'zone_kind': 'a'},
    ]


@pytest.fixture
def workspace(tmp_path: Path, sample_shapes: list[dict]) -> Callable[..., dict]:
    """
        Каталог видео и каталог JSON производства. Возвращает фабрику, создающую видео
        с боевым JSON и (по желанию) JSON рядом с видео.
    """
    videos = tmp_path / 'videos'
    jsons = tmp_path / 'jsons'
    videos.mkdir()
    jsons.mkdir()

    def build(sidecar: bool = False, production: bool = True) -> dict:
        video = videos / VIDEO_NAME
        video.write_bytes(b'not a real video')
        if production:
            write_json(jsons / PRODUCTION_NAME, make_document(sample_shapes))
        if sidecar:
            write_json(videos / 'plant_cam5_x.markup.json', make_document(sample_shapes[:1]))
        return {'video': video, 'videos': videos, 'jsons': jsons,
                'production': jsons / PRODUCTION_NAME, 'sidecar': videos / 'plant_cam5_x.markup.json'}

    return build
