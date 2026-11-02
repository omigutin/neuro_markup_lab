"""
Маршруты NeuroMarkupLab. Тонкие: разбирают запрос и делегируют :class:`MarkupLabService`.

Обработчики синхронные: чтение видео и файлов блокирующее, FastAPI выполняет их в пуле потоков.
"""

__all__ = ['markup_lab_router']

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ..lab import parse_save_request
from ..markup import MarkupError
from ..storage import MarkupVariant
from ..videos import FULL_WIDTH, PREVIEW_WIDTH, first_frame_jpeg
from .web_types import NAV_KEY, PAGE_ROUTE, STATIC_PREFIX, NeuroMarkupLabWebDependencies

markup_lab_router = APIRouter()

# Значения параметра запроса, означающие «да»
_TRUE_VALUES: frozenset[str] = frozenset({'1', 'true', 'on', 'yes'})
_NO_STORE = {'Cache-Control': 'no-store'}


def _deps(request: Request) -> NeuroMarkupLabWebDependencies:
    deps: NeuroMarkupLabWebDependencies = request.app.state.nml_web_deps
    return deps


def _param(request: Request, name: str) -> str:
    return (request.query_params.get(name) or '').strip()


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({'ok': False, 'error': message}, status_code=status, headers=_NO_STORE)


@markup_lab_router.get(PAGE_ROUTE, response_class=HTMLResponse)
def markup_lab_page(request: Request) -> HTMLResponse:
    """ Страница разметки: каталог видео и JSON, список видео, редактор. Данные грузит JS. """
    nav_renderer = request.app.state.nml_nav
    nav_html = nav_renderer(NAV_KEY, '') if nav_renderer else ''
    response: HTMLResponse = request.app.state.nml_jinja.TemplateResponse(
        request, 'neuro_markup_lab/page.html', {'nav': nav_html, 'static': STATIC_PREFIX})
    return response


@markup_lab_router.get(f'{PAGE_ROUTE}/api/videos')
def list_videos(request: Request) -> JSONResponse:
    """ Видео каталога и наличие разметки рядом с видео и в каталоге JSON. """
    recursive = _param(request, 'recursive').lower() in _TRUE_VALUES
    listing = _deps(request).service.list_videos(_param(request, 'path'), recursive, _param(request, 'jsons'))
    return JSONResponse({'ok': not listing.error, **listing.as_dict()}, headers=_NO_STORE)


@markup_lab_router.get(f'{PAGE_ROUTE}/api/markup')
def open_markup(request: Request) -> JSONResponse:
    """ Разметка выбранного варианта для видео: фигуры, схема атрибутов, расхождения типов. """
    try:
        variant = MarkupVariant(_param(request, 'variant'))
    except ValueError:
        return _error('Unknown markup variant')
    try:
        view = _deps(request).service.open(_param(request, 'video'), variant, _param(request, 'jsons'))
    except MarkupError as exc:
        return _error(str(exc), status=404)
    return JSONResponse({'ok': True, **view.as_dict()}, headers=_NO_STORE)


@markup_lab_router.post(f'{PAGE_ROUTE}/api/save')
async def save_markup(request: Request) -> JSONResponse:
    """ Проверка (``dry_run``) или сохранение разметки с приведением типов во всём документе. """
    try:
        payload = await request.json()
    except ValueError:
        return _error('Request body must be JSON')
    if not isinstance(payload, dict):
        return _error('Request body must be a JSON object')
    try:
        save_request = parse_save_request(payload)
    except MarkupError as exc:
        return _error(str(exc))
    try:
        result = await run_in_threadpool(_deps(request).service.save, save_request)
    except MarkupError as exc:
        return _error(str(exc))
    return JSONResponse({'ok': True, **result.as_dict()}, headers=_NO_STORE)


@markup_lab_router.post(f'{PAGE_ROUTE}/api/open-file')
async def open_markup_file(request: Request) -> JSONResponse:
    """ Открывает JSON разметки видео в программе по умолчанию на этом компьютере. """
    try:
        payload = await request.json()
    except ValueError:
        return _error('Request body must be JSON')
    if not isinstance(payload, dict):
        return _error('Request body must be a JSON object')
    try:
        variant = MarkupVariant(payload.get('variant'))
    except ValueError:
        return _error('Unknown markup variant')
    video, jsons_dir = payload.get('video'), payload.get('jsons_dir') or ''
    if not isinstance(video, str) or not isinstance(jsons_dir, str):
        return _error('Fields "video" and "jsons_dir" must be strings')
    try:
        path = await run_in_threadpool(_deps(request).service.open_file, video, variant, jsons_dir)
    except MarkupError as exc:
        return _error(str(exc))
    return JSONResponse({'ok': True, 'path': str(path)}, headers=_NO_STORE)


@markup_lab_router.get(f'{PAGE_ROUTE}/frame')
def video_frame(request: Request) -> Response:
    """ Первый кадр видео в JPEG: ``full=1`` — для редактора, иначе — для карточки. """
    max_width = FULL_WIDTH if _param(request, 'full') else PREVIEW_WIDTH
    data = first_frame_jpeg(Path(_param(request, 'video')), max_width=max_width)
    if data is None:
        return Response(status_code=404)
    return Response(content=data, media_type='image/jpeg', headers=_NO_STORE)
