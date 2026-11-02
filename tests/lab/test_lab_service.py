""" Сервис редактора разметки: список видео, открытие и сохранение разметки. """

import pytest

from neuro_markup_lab.lab import MarkupLabHost, MarkupLabService, SaveRequest
from neuro_markup_lab.markup import AttributeSpec, AttributeType, MarkupError, ShapeChange
from neuro_markup_lab.storage import MarkupVariant

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
    assert video.factory is None and video.production.key == 'plant_cam5'
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


class _Host(MarkupLabHost):
    def __init__(self, key: str | None = None) -> None:
        self.key = key

    def markup_key(self, video):
        return self.key

    def factories(self):
        return ['Plant', 'mill']


def test_list_videos_with_host(workspace):
    ws = workspace(sidecar=False)
    video = MarkupLabService(host=_Host()).list_videos(str(ws['videos']), False, str(ws['jsons'])).videos[0]
    assert video.factory == 'Plant' and video.production.exists
    video = MarkupLabService(host=_Host('other')).list_videos(str(ws['videos']), False, str(ws['jsons'])).videos[0]
    assert video.production.key == 'other' and not video.production.exists


def test_manual_production_key(workspace):
    ws = workspace(sidecar=False)
    (ws['jsons'] / 'line_a.json').write_text((ws['production']).read_text(encoding='utf-8'), encoding='utf-8')
    service = MarkupLabService()
    entry = service.video_entry(str(ws['video']), str(ws['jsons']), production_key='line_a')
    assert entry.production.key == 'line_a' and entry.production.manual and entry.production.exists
    entry = service.video_entry(str(ws['video']), str(ws['jsons']), production_path=str(ws['jsons'] / 'line_a.json'))
    assert entry.production.key == 'line_a'
    view = service.open(str(ws['video']), MarkupVariant.PRODUCTION, str(ws['jsons']), production_key='line_a')
    assert view.location.key == 'line_a'
    with pytest.raises(MarkupError):
        service.video_entry(str(ws['video']), str(ws['jsons']), production_path=str(ws['videos'] / 'x.json'))
    with pytest.raises(MarkupError):
        service.video_entry(str(ws['video']), str(ws['jsons']), production_key='../x')


def test_save_to_manual_production_key(workspace):
    ws = workspace(sidecar=False)
    (ws['jsons'] / 'line_a.json').write_text((ws['production']).read_text(encoding='utf-8'), encoding='utf-8')
    req = SaveRequest(video=ws['video'], base_variant=MarkupVariant.PRODUCTION, target_variant=MarkupVariant.PRODUCTION,
                      jsons_dir=str(ws['jsons']), changes={0: ShapeChange(points=[[1, 1], [2, 2]])}, fields={},
                      dry_run=False, confirm_production=True, production_key='line_a')
    result = MarkupLabService().save(req)
    assert result.saved and result.target.key == 'line_a'
    assert read_json(ws['jsons'] / 'line_a.json')['shapes'][0]['points'] == [[1.0, 1.0], [2.0, 2.0]]
    assert read_json(ws['production'])['shapes'][0]['points'] == [[10, 20], [110, 220]]


def test_video_entry(workspace):
    ws = workspace(sidecar=True)
    entry = MarkupLabService().video_entry(str(ws['video']), str(ws['jsons']))
    assert entry.sidecar.exists and entry.production.exists and entry.relative_dir == ''
    assert MarkupLabService().video_entry(str(ws['video']), '').production.path is None
    with pytest.raises(MarkupError):
        MarkupLabService().video_entry(str(ws['videos'] / 'none.avi'), '')


# ------------------------------------------------------------------- версии и защита от чужих правок

def _save(ws, **kw) -> SaveRequest:
    base = dict(video=ws['video'], base_variant=MarkupVariant.PRODUCTION, target_variant=MarkupVariant.SIDECAR,
                jsons_dir=str(ws['jsons']), changes={}, fields={}, dry_run=False, confirm_production=False)
    base.update(kw)
    return SaveRequest(**base)


def test_sidecar_save_creates_versions(workspace):
    from neuro_markup_lab.storage import SaveMode
    ws = workspace(sidecar=False)
    service = MarkupLabService()
    result = service.save(_save(ws, comment='из боевой'))
    assert result.saved and result.version.number == 1 and result.version.source == 'production'
    change = {0: ShapeChange(points=[[1, 1], [2, 2]])}
    result = service.save(_save(ws, base_variant=MarkupVariant.SIDECAR, base_version=1, changes=change))
    assert result.version.number == 2 and result.version.based_on == 1
    view = service.open(str(ws['video']), MarkupVariant.SIDECAR, str(ws['jsons']))
    assert view.current_version == 2 and view.markup_version == 2 and view.versions_count == 2
    old = service.open(str(ws['video']), MarkupVariant.SIDECAR, str(ws['jsons']), version=1)
    assert old.markup_version == 1 and old.document['shapes'][0]['points'] == [[10, 20], [110, 220]]
    result = service.save(_save(ws, base_variant=MarkupVariant.SIDECAR, base_version=1, mode=SaveMode.OVERWRITE,
                                changes=change))
    assert result.version.number == 1 and service.versions(str(ws['video'])).current == 1
    with pytest.raises(MarkupError):
        service.open(str(ws['video']), MarkupVariant.PRODUCTION, str(ws['jsons']), version=1)


def test_overwrite_current_version_from_production(workspace):
    from neuro_markup_lab.storage import SaveMode
    ws = workspace(sidecar=False)
    service = MarkupLabService()
    service.save(_save(ws))
    service.save(_save(ws, changes={0: ShapeChange(points=[[1, 1], [2, 2]])}))
    result = service.save(_save(ws, mode=SaveMode.OVERWRITE, base_version=2))
    assert result.version.number == 2 and service.versions(str(ws['video'])).current == 2
    assert read_json(ws['sidecar'])['shapes'][0]['points'] == [[10, 20], [110, 220]]
    assert len(service.versions(str(ws['video'])).versions) == 2
    assert service.version_path(str(ws['video']), 1).parent == service.versions_directory(str(ws['video']))
    assert service.working_matches_current(str(ws['video']))
    with pytest.raises(MarkupError):
        service.version_path(str(ws['video']), 9)


def test_conflict_when_file_changed(workspace):
    from neuro_markup_lab.lab import MarkupConflictError
    ws = workspace(sidecar=True)
    service = MarkupLabService()
    view = service.open(str(ws['video']), MarkupVariant.SIDECAR, str(ws['jsons']))
    ws['sidecar'].write_text(ws['sidecar'].read_text(encoding='utf-8') + ' ', encoding='utf-8')
    request = _save(ws, base_variant=MarkupVariant.SIDECAR, expected_hash=view.file_hash)
    with pytest.raises(MarkupConflictError):
        service.save(request)
    assert service.save(_save(ws, base_variant=MarkupVariant.SIDECAR, expected_hash=view.file_hash, force=True)).saved


def test_production_save_keeps_backup(workspace):
    ws = workspace()
    before = ws['production'].read_text(encoding='utf-8')
    req = _save(ws, target_variant=MarkupVariant.PRODUCTION, confirm_production=True,
                changes={0: ShapeChange(points=[[1, 1], [2, 2]])})
    assert MarkupLabService().save(req).saved
    backup = ws['production'].with_name('plant_cam5.json.bak')
    assert backup.read_text(encoding='utf-8') == before
    assert not (ws['videos'] / 'plant_cam5_x_jsons').exists()


def test_make_current_and_update_version(workspace):
    ws = workspace(sidecar=False)
    service = MarkupLabService()
    service.save(_save(ws))
    service.save(_save(ws, changes={0: ShapeChange(points=[[1, 1], [2, 2]])}))
    assert service.make_current_version(str(ws['video']), 1).number == 1
    assert read_json(ws['sidecar'])['shapes'][0]['points'] == [[10, 20], [110, 220]]
    assert service.update_version(str(ws['video']), 2, pinned=True).pinned
