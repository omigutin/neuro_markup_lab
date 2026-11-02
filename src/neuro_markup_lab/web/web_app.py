"""
Приложение редактора разметки: отдельное или встроенное в другое веб-приложение.

Страница и API считаются от корня приложения редактора, поэтому его можно подключить
к хозяину под любым префиксом (:func:`mount_app`) или запустить само по себе (:func:`create_app`).
"""

__all__ = ['create_app', 'mount_app']

from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from ..lab import MarkupLabHost, MarkupLabService
from .web_no_cache_static import NoCacheStaticFiles
from .web_path_picker import pick_path
from .web_routes import markup_lab_router
from .web_types import APP_ID, DEFAULT_PREFIX, NavRenderer, NeuroMarkupLabWebDependencies, PathPicker

_WEB_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _WEB_DIR / 'templates'
_STATIC_DIR = _WEB_DIR / 'static'


def create_app(service: MarkupLabService | None = None, *, host: MarkupLabHost | None = None,
               nav_renderer: NavRenderer | None = None, path_picker: PathPicker | None = None) -> FastAPI:
    """
        Приложение редактора: страница ``/``, API ``/api/...``, кадр ``/frame``, статика ``/static``.
        ``host`` — данные приложения-хозяина (ключ боевой разметки, производства); ``service`` — свой
        сервис вместо сервиса по умолчанию (тогда ``host`` передаётся в него); ``nav_renderer`` —
        навигация хозяина над страницей; ``path_picker`` — окно выбора каталога и файла.
    """
    if service is not None and host is not None:
        raise ValueError('Pass host to MarkupLabService when a custom service is given')
    app = FastAPI(title=APP_ID, docs_url='/api/docs', redoc_url=None, openapi_url='/api/openapi.json')
    app.state.nml = NeuroMarkupLabWebDependencies(
        service=service or MarkupLabService(host=host), nav_renderer=nav_renderer,
        path_picker=path_picker or pick_path)
    app.state.nml_jinja = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    app.mount('/static', NoCacheStaticFiles(directory=str(_STATIC_DIR)), name='static')
    app.include_router(markup_lab_router)
    return app


def mount_app(parent: FastAPI, prefix: str = DEFAULT_PREFIX, service: MarkupLabService | None = None, *,
              host: MarkupLabHost | None = None, nav_renderer: NavRenderer | None = None,
              path_picker: PathPicker | None = None) -> FastAPI:
    """
        Встраивает редактор в приложение ``parent`` по адресу ``prefix`` (страница — ``prefix + '/'``).
        Возвращает приложение редактора.
    """
    path = '/' + prefix.strip('/')
    if path == '/':
        raise ValueError('Prefix must not be empty: mount the app returned by create_app() instead')
    app = create_app(service, host=host, nav_renderer=nav_renderer, path_picker=path_picker)
    parent.mount(path, app, name=APP_ID)
    return app
