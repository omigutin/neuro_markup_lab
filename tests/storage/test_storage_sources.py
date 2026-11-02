""" Источники разметки: JSON рядом с видео и боевой JSON производства. """

from pathlib import Path

import pytest

from neuro_markup_lab.markup import MarkupError
from neuro_markup_lab.storage import CameraKey, MarkupVariant, ProductionMarkupSource, SidecarMarkupSource

from ..conftest import make_document, read_json


def test_sidecar_location_beside_video(workspace):
    ws = workspace(sidecar=True)
    location = SidecarMarkupSource().locate(ws['video'])
    assert location.variant == MarkupVariant.SIDECAR
    assert location.path == ws['sidecar'] and location.exists and location.name == 'plant_cam5_x.markup.json'


def test_sidecar_missing(workspace):
    ws = workspace(sidecar=False)
    location = SidecarMarkupSource().locate(ws['video'])
    assert not location.exists and location.path == ws['sidecar']
    with pytest.raises(MarkupError):
        SidecarMarkupSource().load(ws['video'])


def test_production_flat_directory(workspace):
    ws = workspace()
    location = ProductionMarkupSource(ws['jsons']).locate(ws['video'])
    assert location.path == ws['jsons'] / 'plant_cam5.json' and location.exists


def test_production_without_jsons_dir(workspace):
    ws = workspace()
    location = ProductionMarkupSource(None).locate(ws['video'])
    assert location.path is None and not location.exists and location.reason
    with pytest.raises(MarkupError):
        ProductionMarkupSource(None).save(ws['video'], make_document([]))


def test_production_camera_not_parsed(tmp_path):
    location = ProductionMarkupSource(tmp_path).locate(Path(tmp_path / 'clip.avi'))
    assert location.path is None and location.reason


def test_save_and_load_roundtrip(workspace):
    ws = workspace(production=False)
    source = SidecarMarkupSource()
    document = make_document([{'label': 'зона', 'points': [[1, 2]], 'shape_type': 'point'}])
    path = source.save(ws['video'], document)
    assert path == ws['sidecar']
    assert source.load(ws['video']) == document
    # Кириллица — как есть, без \u-экранирования
    assert 'зона' in path.read_text(encoding='utf-8')
    assert read_json(path)['imageWidth'] == 1920


def test_production_uses_camera_resolver(workspace):
    ws = workspace()
    source = ProductionMarkupSource(ws['jsons'], camera_resolver=lambda _path: CameraKey('plant', '5'))
    assert source.locate(ws['jsons'] / 'any.avi').path == ws['jsons'] / 'plant_cam5.json'
