""" Камера видео по имени и пути файла. """

from pathlib import Path

import pytest

from neuro_markup_lab.storage import CameraKey, CameraNameParser


@pytest.mark.parametrize(('path', 'expected'), [
    ('/v/plant_cam5_x.avi', CameraKey('plant', '5')),
    ('/v/Plant-CAM12.mp4', CameraKey('plant', '12')),
    ('/v/cam5_x.avi', None),
    ('/v/plant_x.avi', None),
    ('/v/plant_cam1234.avi', None),
])
def test_factory_before_cam(path, expected):
    assert CameraNameParser()(Path(path)) == expected


def test_known_factories_from_path():
    parser = CameraNameParser(['plant', 'mill'])
    assert parser(Path('/data/mill/ml_cam3_p10.avi')) == CameraKey('mill', '3')
    assert parser(Path('/data/other/ml_cam3.avi')) is None


def test_known_factory_nearest_to_file():
    parser = CameraNameParser(['plant', 'mill'])
    assert parser(Path('/plant/mill_cam3.avi')) == CameraKey('mill', '3')
