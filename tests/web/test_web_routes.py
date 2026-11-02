""" Маршруты редактора разметки поверх временного каталога. """

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from neuro_markup_lab.lab import MarkupLabService
from neuro_markup_lab.web import NeuroMarkupLabWebDependencies, mount

from ..conftest import read_json


class _Opener:
    def __init__(self) -> None:
        self.opened = []

    def open(self, path) -> None:
        self.opened.append(path)


@pytest.fixture
def opener() -> _Opener:
    return _Opener()


@pytest.fixture
def client(opener) -> TestClient:
    app = FastAPI()
    deps = NeuroMarkupLabWebDependencies(service=MarkupLabService(opener=opener))
    mount(app, nav_renderer=lambda active, user: f'<nav data-active="{active}"></nav>', deps=deps)
    return TestClient(app)


def test_page_renders_with_nav_and_static(client):
    response = client.get('/neuro-markup-lab')
    assert response.status_code == 200
    html = response.text
    assert 'data-active="markup"' in html
    names = ('neuro_markup_lab.css', 'neuro_markup_lab_shapes.js', 'neuro_markup_lab_editor.js',
             'neuro_markup_lab_page.js')
    for name in names:
        assert f'/neuro-markup-lab-static/{name}' in html
        static = client.get(f'/neuro-markup-lab-static/{name}')
        assert static.status_code == 200 and static.headers['cache-control'] == 'no-store'
    assert 'id="nml-editor"' in html
    assert 'data-save="sidecar"' in html and 'data-save="production"' in html


def test_videos_api(client, workspace):
    ws = workspace(sidecar=True)
    data = client.get('/neuro-markup-lab/api/videos',
                      params={'path': str(ws['videos']), 'recursive': '1', 'jsons': str(ws['jsons'])}).json()
    assert data['ok'] and data['recursive'] and len(data['videos']) == 1
    assert data['videos'][0]['production']['exists'] and data['videos'][0]['default_variant'] == 'sidecar'


def test_videos_api_error(client, tmp_path):
    data = client.get('/neuro-markup-lab/api/videos', params={'path': str(tmp_path / 'none')}).json()
    assert data['ok'] is False and data['error']


def test_markup_api(client, workspace):
    ws = workspace()
    response = client.get('/neuro-markup-lab/api/markup',
                          params={'video': str(ws['video']), 'variant': 'production', 'jsons': str(ws['jsons'])})
    data = response.json()
    assert response.status_code == 200 and data['ok'] and len(data['shapes']) == 2
    assert data['report']['conversions'][0]['field'] == 'wz'
    bad = client.get('/neuro-markup-lab/api/markup', params={'video': str(ws['video']), 'variant': 'x'})
    assert bad.status_code == 400
    missing = client.get('/neuro-markup-lab/api/markup', params={'video': str(ws['video']), 'variant': 'sidecar'})
    assert missing.status_code == 404


def test_save_api_flow(client, workspace):
    ws = workspace()
    body = {'video': str(ws['video']), 'jsons_dir': str(ws['jsons']), 'base_variant': 'production',
            'target_variant': 'production',
            'changes': {'0': {'points': [[1, 1], [5, 5]], 'shape_type': 'rectangle'}}}
    check = client.post('/neuro-markup-lab/api/save', json={**body, 'dry_run': True}).json()
    assert check['ok'] and not check['saved'] and check['target']['exists']
    refused = client.post('/neuro-markup-lab/api/save', json=body).json()
    assert refused['ok'] is False
    saved = client.post('/neuro-markup-lab/api/save', json={**body, 'confirm_production': True}).json()
    assert saved['ok'] and saved['saved']
    document = read_json(ws['production'])
    assert document['shapes'][0]['points'] == [[1.0, 1.0], [5.0, 5.0]] and document['shapes'][0]['wz'] == 1


def test_save_api_rejects_bad_body(client):
    assert client.post('/neuro-markup-lab/api/save', content=b'not json').json()['ok'] is False
    assert client.post('/neuro-markup-lab/api/save', json=[1]).json()['ok'] is False
    assert client.post('/neuro-markup-lab/api/save', json={'video': ''}).json()['ok'] is False


def test_frame_missing_video(client, tmp_path):
    assert client.get('/neuro-markup-lab/frame', params={'video': str(tmp_path / 'none.avi')}).status_code == 404


def test_open_file_api(client, opener, workspace):
    ws = workspace()
    body = {'video': str(ws['video']), 'variant': 'production', 'jsons_dir': str(ws['jsons'])}
    data = client.post('/neuro-markup-lab/api/open-file', json=body).json()
    assert data['ok'] and opener.opened == [ws['production']]
    assert client.post('/neuro-markup-lab/api/open-file', json={**body, 'variant': 'x'}).json()['ok'] is False
    assert client.post('/neuro-markup-lab/api/open-file', json={**body, 'variant': 'sidecar'}).json()['ok'] is False
    assert client.post('/neuro-markup-lab/api/open-file', json=[1]).json()['ok'] is False
