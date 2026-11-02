""" Подключение NeuroMarkupLab к web-приложению хоста. """

__all__ = ['build_web_dependencies', 'mount']

from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from ..lab import MarkupLabService
from .web_no_cache_static import NoCacheStaticFiles
from .web_routes import markup_lab_router
from .web_types import STATIC_PREFIX, NavRenderer, NeuroMarkupLabWebDependencies

_WEB_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _WEB_DIR / 'templates'
_STATIC_DIR = _WEB_DIR / 'static'


def build_web_dependencies() -> NeuroMarkupLabWebDependencies:
    """ Зависимости маршрутов по умолчанию. """
    return NeuroMarkupLabWebDependencies(service=MarkupLabService())


def mount(app: FastAPI, *, nav_renderer: NavRenderer | None = None,
          deps: NeuroMarkupLabWebDependencies | None = None) -> None:
    """ Регистрирует страницу разметки, её API и статику в ``app``. """
    app.state.nml_web_deps = deps or build_web_dependencies()
    app.state.nml_jinja = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    app.state.nml_nav = nav_renderer
    app.mount(STATIC_PREFIX, NoCacheStaticFiles(directory=str(_STATIC_DIR)), name='nml_static')
    app.include_router(markup_lab_router)
