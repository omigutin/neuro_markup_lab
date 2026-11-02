""" Приложение редактора: отдельное и встроенное под префиксом. """

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from neuro_markup_lab.lab import MarkupLabService
from neuro_markup_lab.web import DEFAULT_PREFIX, create_app, mount_app


def test_create_app_serves_page_at_root():
    client = TestClient(create_app())
    assert client.get('/').status_code == 200
    assert client.get('/static/neuro_markup_lab_shapes.js').status_code == 200
    assert client.get('/api/ping').json()['app'] == 'neuro_markup_lab'


def test_mount_app_default_prefix_and_service():
    parent = FastAPI()
    service = MarkupLabService()
    app = mount_app(parent, service=service)
    assert app.state.nml.service is service and app.state.nml.nav_renderer is None
    assert TestClient(parent).get(f'{DEFAULT_PREFIX}/api/ping').status_code == 200


def test_mount_app_normalizes_prefix():
    parent = FastAPI()
    mount_app(parent, 'tools/markup/')
    assert TestClient(parent).get('/tools/markup/api/ping').status_code == 200


@pytest.mark.parametrize('prefix', ['', '/'])
def test_mount_app_rejects_empty_prefix(prefix):
    with pytest.raises(ValueError):
        mount_app(FastAPI(), prefix)


def test_two_apps_are_independent():
    parent = FastAPI()
    mount_app(parent, '/a', nav_renderer=lambda: '<nav>A</nav>')
    mount_app(parent, '/b')
    client = TestClient(parent)
    assert '<nav>A</nav>' in client.get('/a/').text
    assert '<nav>A</nav>' not in client.get('/b/').text
