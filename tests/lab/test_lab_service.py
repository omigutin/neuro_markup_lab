""" Сервис редактора разметки: список видео, открытие и сохранение разметки. """

import pytest

from neuro_markup_lab.lab import MarkupLabService, SaveRequest
from neuro_markup_lab.markup import AttributeSpec, AttributeType, MarkupError, ShapeChange
from neuro_markup_lab.storage import CameraNameParser, MarkupVariant

from ..conftest import read_json


def request(ws, base=MarkupVariant.PRODUCTION, target=MarkupVariant.SIDECAR, changes=None, fields=None,
            dry_run=False, confirm=False) -> SaveRequest:
    return SaveRequest(video=ws['video'], base_variant=base, target_variant=target, jsons_dir=str(ws['jsons']),
                       changes=changes or {}, fields=fields or {}, dry_run=dry_run, confirm_production=confirm)


# ------------------------------------------------------------------- список

def test_list_videos_with_markup(workspace):
    ws = workspace(sidecar=True)
    listing = MarkupLabService().list_videos(str(ws['videos']), False, str(ws['jsons']))
    assert not listing.error and not listing.jsons_error
    video = listing.videos[0]
    assert (video.factory, video.cam_id) == ('plant', '5')
    assert video.sidecar.exists and video.production.exists
    assert video.default_variant == MarkupVariant.SIDECAR
    assert listing.as_dict()['videos'][0]['default_variant'] == 'sidecar'


def test_list_videos_default_production_and_no_jsons_dir(workspace):
    ws = workspace(sidecar=False)
    service = MarkupLabService()
    listing = service.list_videos(str(ws['videos']), False, str(ws['jsons']))
    assert listing.videos[0].default_variant == MarkupVariant.PRODUCTION
    listing = service.list_videos(str(ws['videos']), False, '')
    assert listing.videos[0].default_variant is None and not listing.jsons_error
    assert service.list_videos(str(ws['videos']), False, str(ws['jsons'] / 'none')).jsons_error


def test_list_videos_errors(tmp_path):
    service = MarkupLabService()
    assert service.list_videos('', False, '').error
    assert service.list_videos(str(tmp_path / 'none'), False, '').error


# ------------------------------------------------------------------- открытие

def test_open_reports_type_mismatch_without_changing_document(workspace):
    ws = workspace()
    view = MarkupLabService().open(str(ws['video']), MarkupVariant.PRODUCTION, str(ws['jsons']))
    data = view.as_dict()
    assert data['location']['variant'] == 'production'
    assert data['image_width'] == 1920 and len(data['shapes']) == 2
    assert data['shapes'][0]['attributes']['wz'] == '1'
    assert 'points' not in data['shapes'][0]['attributes']
    assert [c['field'] for c in data['report']['conversions']] == ['wz']
    assert [s['name'] for s in data['schema']['document']] == ['zone_kind']


def test_open_missing_variant(workspace):
    ws = workspace(sidecar=False)
    with pytest.raises(MarkupError):
        MarkupLabService().open(str(ws['video']), MarkupVariant.SIDECAR, str(ws['jsons']))
    with pytest.raises(MarkupError):
        MarkupLabService().open(str(ws['videos'] / 'none.avi'), MarkupVariant.PRODUCTION, str(ws['jsons']))


# ------------------------------------------------------------------- сохранение

def test_save_production_to_sidecar_normalizes_whole_document(workspace):
    ws = workspace()
    original = ws['production'].read_text(encoding='utf-8')
    result = MarkupLabService().save(request(ws, changes={1: ShapeChange(attributes={
        'label': 'input', 'group_id': None, 'description': '', 'flags': {}, 'mask': None, 'position': 'right',
        'wz': 3, 'zone_kind': 'b', 'new_field': 7})}))
    assert result.saved and result.target.variant == MarkupVariant.SIDECAR
    saved = read_json(ws['sidecar'])
    # Нередактированная фигура тоже приведена: wz "1" → 1
    assert saved['shapes'][0]['wz'] == 1
    assert saved['shapes'][1]['wz'] == 3 and saved['shapes'][1]['new_field'] == 7
    assert saved['imagePath'] == 'cam.jpg' and saved['lineColor'] == [0, 255, 0, 128]
    # Боевой JSON не тронут
    assert ws['production'].read_text(encoding='utf-8') == original


def test_dry_run_writes_nothing(workspace):
    ws = workspace()
    result = MarkupLabService().save(request(ws, dry_run=True))
    assert not result.saved and not ws['sidecar'].exists()
    assert [c.field for c in result.report.conversions] == ['wz']
    assert result.target.path == ws['sidecar'] and not result.target.exists


def test_problem_blocks_save(workspace):
    ws = workspace()
    attributes = {'label': 'crop', 'wz': 'abc'}
    result = MarkupLabService().save(request(ws, changes={0: ShapeChange(attributes=attributes)}))
    assert not result.saved and result.report.problems[0].field == 'wz'
    assert not ws['sidecar'].exists()


def test_production_requires_confirmation(workspace):
    ws = workspace(sidecar=True)
    service = MarkupLabService()
    with pytest.raises(MarkupError):
        service.save(request(ws, base=MarkupVariant.SIDECAR, target=MarkupVariant.PRODUCTION))
    result = service.save(request(ws, base=MarkupVariant.SIDECAR, target=MarkupVariant.PRODUCTION, confirm=True))
    assert result.saved and result.target.exists
    # Боевой JSON заменён содержимым JSON рядом с видео
    assert len(read_json(ws['production'])['shapes']) == 1


def test_field_type_override_converts_values(workspace):
    ws = workspace()
    fields = {'zone_kind': AttributeSpec('zone_kind', AttributeType.INT, nullable=True)}
    result = MarkupLabService().save(request(ws, fields=fields, dry_run=True))
    assert [p.field for p in result.report.problems] == ['zone_kind']


def test_target_unknown_without_jsons_dir(workspace):
    ws = workspace(sidecar=True)
    bad = SaveRequest(video=ws['video'], base_variant=MarkupVariant.SIDECAR, target_variant=MarkupVariant.PRODUCTION,
                      jsons_dir='', changes={}, fields={}, dry_run=True, confirm_production=True)
    with pytest.raises(MarkupError):
        MarkupLabService().save(bad)


def test_missing_base(workspace):
    ws = workspace(sidecar=False)
    with pytest.raises(MarkupError):
        MarkupLabService().save(request(ws, base=MarkupVariant.SIDECAR))


# ------------------------------------------------------------------- открытие файла

class _Opener:
    def __init__(self) -> None:
        self.opened = []

    def open(self, path) -> None:
        self.opened.append(path)


def test_open_file_opens_located_markup_only(workspace):
    ws = workspace(sidecar=False)
    opener = _Opener()
    service = MarkupLabService(opener=opener)
    assert service.open_file(str(ws['video']), MarkupVariant.PRODUCTION, str(ws['jsons'])) == ws['production']
    assert opener.opened == [ws['production']]
    with pytest.raises(MarkupError):
        service.open_file(str(ws['video']), MarkupVariant.SIDECAR, str(ws['jsons']))
    with pytest.raises(MarkupError):
        service.open_file(str(ws['production']), MarkupVariant.PRODUCTION, str(ws['jsons']))


def test_list_videos_with_camera_resolver(workspace):
    ws = workspace(sidecar=False)
    service = MarkupLabService(camera_resolver=CameraNameParser(['mill']))
    video = service.list_videos(str(ws['videos']), False, str(ws['jsons'])).videos[0]
    assert (video.factory, video.cam_id) == (None, None)
    assert video.production.path is None and video.default_variant is None


def test_video_entry(workspace):
    ws = workspace(sidecar=True)
    entry = MarkupLabService().video_entry(str(ws['video']), str(ws['jsons']))
    assert entry.sidecar.exists and entry.production.exists and entry.relative_dir == ''
    assert MarkupLabService().video_entry(str(ws['video']), '').production.path is None
    with pytest.raises(MarkupError):
        MarkupLabService().video_entry(str(ws['videos'] / 'none.avi'), '')
