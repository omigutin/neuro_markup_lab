""" Маршруты редактора разметки поверх временного каталога. """

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from neuro_markup_lab.lab import MarkupLabService
from neuro_markup_lab.web import PathPickerError, PickKind, mount_app

from ..conftest import read_json


class _Opener:
    def __init__(self) -> None:
        self.opened = []

    def open(self, path) -> None:
        self.opened.append(path)


@pytest.fixture
def opener() -> _Opener:
    return _Opener()


# Префикс встраивания в тестах: проверяет, что страница и API не зависят от адреса
PREFIX = '/x/lab'


class _Picker:
    def __init__(self) -> None:
        self.calls: list[tuple[PickKind, str]] = []
        self.result: str | None = '/picked'
        self.error = False

    def __call__(self, kind: PickKind, initial: str) -> str | None:
        self.calls.append((kind, initial))
        if self.error:
            raise PathPickerError('no tkinter')
        return self.result


@pytest.fixture
def picker() -> _Picker:
    return _Picker()


@pytest.fixture
def client(opener, picker) -> TestClient:
    app = FastAPI()
    mount_app(app, PREFIX, MarkupLabService(opener=opener), nav_renderer=lambda: '<nav data-active="markup"></nav>',
              path_picker=picker)
    return TestClient(app)


def test_page_renders_with_nav_and_relative_static(client):
    response = client.get(f'{PREFIX}/')
    assert response.status_code == 200
    html = response.text
    assert 'data-active="markup"' in html
    names = ('neuro_markup_lab.css', 'neuro_markup_lab_shapes.js', 'neuro_markup_lab_editor.js',
             'neuro_markup_lab_frame.js', 'neuro_markup_lab_page.js')
    for name in names:
        assert f'"static/{name}"' in html
        static = client.get(f'{PREFIX}/static/{name}')
        assert static.status_code == 200 and static.headers['cache-control'] == 'no-store'
    # Абсолютных адресов на странице нет: её можно встроить под любым префиксом
    assert 'href="/' not in html and 'src="/' not in html


def test_page_redirects_to_trailing_slash(client):
    response = client.get(PREFIX, follow_redirects=False)
    assert response.status_code in (307, 308) and response.headers['location'].endswith(f'{PREFIX}/')


def test_editor_markup_is_static(client):
    html = client.get(f'{PREFIX}/static/neuro_markup_lab_editor.html').text
    assert 'id="nml-editor"' in html and 'data-save="sidecar"' in html and 'data-save="production"' in html
    assert '{#' not in html and '{%' not in html


def test_ping(client):
    assert client.get(f'{PREFIX}/api/ping').json()['app'] == 'neuro_markup_lab'


def test_locations_api(client, workspace):
    ws = workspace(sidecar=True)
    data = client.get(f'{PREFIX}/api/locations', params={'video': str(ws['video']), 'jsons': str(ws['jsons'])}).json()
    assert data['ok'] and data['sidecar']['exists'] and data['production']['exists']
    assert data['default_variant'] == 'sidecar' and data['production']['key'] == 'plant_cam5'
    missing = client.get(f'{PREFIX}/api/locations', params={'video': str(ws['videos'] / 'none.avi')})
    assert missing.status_code == 404


def test_pick_api(client, picker):
    assert client.post(f'{PREFIX}/api/pick', json={'initial': 'D:/v'}).json() == {'ok': True, 'path': '/picked'}
    assert picker.calls == [(PickKind.DIR, 'D:/v')]
    client.post(f'{PREFIX}/api/pick', json={'kind': 'json', 'initial': 'D:/j'})
    assert picker.calls[-1] == (PickKind.JSON, 'D:/j')
    assert client.post(f'{PREFIX}/api/pick', json={'kind': 'x'}).json()['ok'] is False
    picker.result = None
    assert client.post(f'{PREFIX}/api/pick', json={}).json() == {'ok': True, 'path': None}
    picker.error = True
    response = client.post(f'{PREFIX}/api/pick', json={})
    assert response.status_code == 503 and response.json()['ok'] is False
    assert client.post(f'{PREFIX}/api/pick', json={'initial': 5}).json()['ok'] is False


def test_videos_api(client, workspace):
    ws = workspace(sidecar=True)
    data = client.get(f'{PREFIX}/api/videos',
                      params={'path': str(ws['videos']), 'recursive': '1', 'jsons': str(ws['jsons'])}).json()
    assert data['ok'] and data['recursive'] and len(data['videos']) == 1
    assert data['videos'][0]['production']['exists'] and data['videos'][0]['default_variant'] == 'sidecar'


def test_videos_api_error(client, tmp_path):
    data = client.get(f'{PREFIX}/api/videos', params={'path': str(tmp_path / 'none')}).json()
    assert data['ok'] is False and data['error']


def test_markup_api(client, workspace):
    ws = workspace()
    response = client.get(f'{PREFIX}/api/markup',
                          params={'video': str(ws['video']), 'variant': 'production', 'jsons': str(ws['jsons'])})
    data = response.json()
    assert response.status_code == 200 and data['ok'] and len(data['shapes']) == 2
    assert data['report']['conversions'][0]['field'] == 'wz'
    bad = client.get(f'{PREFIX}/api/markup', params={'video': str(ws['video']), 'variant': 'x'})
    assert bad.status_code == 400
    missing = client.get(f'{PREFIX}/api/markup', params={'video': str(ws['video']), 'variant': 'sidecar'})
    assert missing.status_code == 404


def test_save_api_flow(client, workspace):
    ws = workspace()
    body = {'video': str(ws['video']), 'jsons_dir': str(ws['jsons']), 'base_variant': 'production',
            'target_variant': 'production',
            'changes': {'0': {'points': [[1, 1], [5, 5]], 'shape_type': 'rectangle'}}}
    check = client.post(f'{PREFIX}/api/save', json={**body, 'dry_run': True}).json()
    assert check['ok'] and not check['saved'] and check['target']['exists']
    refused = client.post(f'{PREFIX}/api/save', json=body).json()
    assert refused['ok'] is False
    saved = client.post(f'{PREFIX}/api/save', json={**body, 'confirm_production': True}).json()
    assert saved['ok'] and saved['saved']
    document = read_json(ws['production'])
    assert document['shapes'][0]['points'] == [[1.0, 1.0], [5.0, 5.0]] and document['shapes'][0]['wz'] == 1


def test_save_api_rejects_bad_body(client):
    assert client.post(f'{PREFIX}/api/save', content=b'not json').json()['ok'] is False
    assert client.post(f'{PREFIX}/api/save', json=[1]).json()['ok'] is False
    assert client.post(f'{PREFIX}/api/save', json={'video': ''}).json()['ok'] is False


def test_frame_missing_video(client, tmp_path):
    assert client.get(f'{PREFIX}/frame', params={'video': str(tmp_path / 'none.avi')}).status_code == 404


def test_open_file_api(client, opener, workspace):
    ws = workspace()
    body = {'video': str(ws['video']), 'variant': 'production', 'jsons_dir': str(ws['jsons'])}
    data = client.post(f'{PREFIX}/api/open-file', json=body).json()
    assert data['ok'] and opener.opened == [ws['production']]
    assert client.post(f'{PREFIX}/api/open-file', json={**body, 'variant': 'x'}).json()['ok'] is False
    assert client.post(f'{PREFIX}/api/open-file', json={**body, 'variant': 'sidecar'}).json()['ok'] is False
    assert client.post(f'{PREFIX}/api/open-file', json=[1]).json()['ok'] is False


def test_locations_and_markup_with_manual_key(client, workspace):
    ws = workspace()
    (ws['jsons'] / 'line_a.json').write_text(ws['production'].read_text(encoding='utf-8'), encoding='utf-8')
    params = {'video': str(ws['video']), 'jsons': str(ws['jsons'])}
    chosen = str(ws['jsons'] / 'line_a.json')
    data = client.get(f'{PREFIX}/api/locations', params={**params, 'production': chosen}).json()
    assert data['production']['key'] == 'line_a' and data['production']['manual']
    outside = str(ws['videos'] / 'a.json')
    bad = client.get(f'{PREFIX}/api/locations', params={**params, 'production': outside})
    assert bad.status_code == 404
    markup = client.get(f'{PREFIX}/api/markup', params={**params, 'variant': 'production', 'key': 'line_a'}).json()
    assert markup['location']['key'] == 'line_a'


def test_open_video_api(client, opener, workspace):
    ws = workspace()
    data = client.post(f'{PREFIX}/api/open-video', json={'video': str(ws['video'])}).json()
    assert data['ok'] and opener.opened == [ws['video']]
    assert client.post(f'{PREFIX}/api/open-video', json={'video': str(ws['production'])}).json()['ok'] is False
    assert client.post(f'{PREFIX}/api/open-video', json={'video': 5}).json()['ok'] is False


def test_versions_api(client, workspace):
    ws = workspace(sidecar=False)
    body = {'video': str(ws['video']), 'jsons_dir': str(ws['jsons']), 'base_variant': 'production',
            'target_variant': 'sidecar', 'comment': 'первая'}
    assert client.post(f'{PREFIX}/api/save', json=body).json()['version']['number'] == 1
    assert client.post(f'{PREFIX}/api/save', json={**body, 'base_variant': 'sidecar', 'base_version': 1}).json()['ok']
    data = client.get(f'{PREFIX}/api/versions', params={'video': str(ws['video'])}).json()
    assert data['current'] == 2 and [v['number'] for v in data['versions']] == [1, 2]
    assert data['versions'][0]['comment'] == 'первая'
    one = client.get(f'{PREFIX}/api/markup', params={'video': str(ws['video']), 'variant': 'sidecar', 'version': 1})
    assert one.json()['markup_version'] == 1 and one.json()['current_version'] == 2
    assert client.post(f'{PREFIX}/api/versions/current', json={'video': str(ws['video']), 'number': 1}).json()['ok']
    upd = client.post(f'{PREFIX}/api/versions/update', json={'video': str(ws['video']), 'number': 1, 'pinned': True})
    assert upd.json()['version']['pinned']
    assert client.post(f'{PREFIX}/api/versions/current', json={'video': str(ws['video'])}).json()['ok'] is False
    bad = client.get(f'{PREFIX}/api/markup', params={'video': str(ws['video']), 'variant': 'sidecar', 'version': 'x'})
    assert bad.status_code == 404


def test_save_conflict_api(client, workspace):
    ws = workspace(sidecar=True)
    view = client.get(f'{PREFIX}/api/markup', params={'video': str(ws['video']), 'variant': 'sidecar'}).json()
    ws['sidecar'].write_text('{"shapes": []}', encoding='utf-8')
    body = {'video': str(ws['video']), 'base_variant': 'sidecar', 'target_variant': 'sidecar',
            'expected_hash': view['file_hash']}
    response = client.post(f'{PREFIX}/api/save', json=body)
    assert response.status_code == 409 and response.json()['conflict']
