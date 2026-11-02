"""
Маршруты редактора разметки. Тонкие: разбирают запрос и делегируют :class:`MarkupLabService`.

Адреса считаются от корня приложения редактора: при встраивании под префиксом страница
доступна по ``<префикс>/``, а её HTML и JS обращаются к API относительными адресами.
Обработчики синхронные: чтение видео и файлов блокирующее, FastAPI выполняет их в пуле потоков.
"""

__all__ = ['markup_lab_router']

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from .. import __version__
from ..lab import parse_save_request
from ..markup import MarkupError
from ..storage import MarkupVariant
from ..videos import FULL_WIDTH, PREVIEW_WIDTH, first_frame_jpeg
from .web_path_picker_error import PathPickerError
from .web_types import APP_ID, NeuroMarkupLabWebDependencies, PickKind

markup_lab_router = APIRouter()

# Значения параметра запроса, означающие «да»
_TRUE_VALUES: frozenset[str] = frozenset({'1', 'true', 'on', 'yes'})
_NO_STORE = {'Cache-Control': 'no-store'}
# Код перенаправления на адрес страницы со «/» на конце (метод запроса сохраняется)
_REDIRECT_STATUS = 307


def _deps(request: Request) -> NeuroMarkupLabWebDependencies:
    deps: NeuroMarkupLabWebDependencies = request.app.state.nml
    return deps


def _param(request: Request, name: str) -> str:
    return (request.query_params.get(name) or '').strip()


def _error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({'ok': False, 'error': message}, status_code=status, headers=_NO_STORE)


async def _json_object(request: Request) -> dict[str, Any] | JSONResponse:
    """ Тело запроса — JSON-объект, иначе ответ с ошибкой. """
    try:
        payload = await request.json()
    except ValueError:
        return _error('Request body must be JSON')
    if not isinstance(payload, dict):
        return _error('Request body must be a JSON object')
    return payload


@markup_lab_router.get('/', response_class=HTMLResponse)
def markup_lab_page(request: Request) -> Response:
    """ Страница разметки: каталог видео и JSON, список видео, редактор. Данные грузит JS. """
    # Адреса на странице относительные, поэтому адрес страницы должен заканчиваться на «/»
    if not request.url.path.endswith('/'):
        return RedirectResponse(str(request.url.replace(path=request.url.path + '/')), status_code=_REDIRECT_STATUS)
    nav_renderer = _deps(request).nav_renderer
    response: HTMLResponse = request.app.state.nml_jinja.TemplateResponse(
        request, 'neuro_markup_lab/page.html', {'nav': nav_renderer() if nav_renderer else ''},
        headers=_NO_STORE)
    return response


@markup_lab_router.get('/api/ping')
def ping() -> JSONResponse:
    """ Кто отвечает на порту: отдельный запуск узнаёт по нему уже работающий редактор. """
    return JSONResponse({'app': APP_ID, 'version': __version__})


@markup_lab_router.get('/api/videos')
def list_videos(request: Request) -> JSONResponse:
    """ Видео каталога и наличие разметки рядом с видео и в каталоге JSON. """
    recursive = _param(request, 'recursive').lower() in _TRUE_VALUES
    listing = _deps(request).service.list_videos(_param(request, 'path'), recursive, _param(request, 'jsons'))
    return JSONResponse({'ok': not listing.error, **listing.as_dict()}, headers=_NO_STORE)


@markup_lab_router.get('/api/locations')
def video_locations(request: Request) -> JSONResponse:
    """
        Где лежит разметка одного видео. ``key`` — боевая разметка, выбранная вручную;
        ``production`` — путь выбранного файла (должен лежать в каталоге боевых JSON).
    """
    try:
        entry = _deps(request).service.video_entry(
            _param(request, 'video'), _param(request, 'jsons'), production_key=_param(request, 'key') or None,
            production_path=_param(request, 'production') or None)
    except MarkupError as exc:
        return _error(str(exc), status=404)
    return JSONResponse({'ok': True, **entry.as_dict()}, headers=_NO_STORE)


@markup_lab_router.get('/api/markup')
def open_markup(request: Request) -> JSONResponse:
    """ Разметка выбранного варианта для видео: фигуры, схема атрибутов, расхождения типов. """
    try:
        variant = MarkupVariant(_param(request, 'variant'))
    except ValueError:
        return _error('Unknown markup variant')
    try:
        view = _deps(request).service.open(_param(request, 'video'), variant, _param(request, 'jsons'),
                                           production_key=_param(request, 'key') or None)
    except MarkupError as exc:
        return _error(str(exc), status=404)
    return JSONResponse({'ok': True, **view.as_dict()}, headers=_NO_STORE)


@markup_lab_router.post('/api/save')
async def save_markup(request: Request) -> JSONResponse:
    """ Проверка (``dry_run``) или сохранение разметки с приведением типов во всём документе. """
    payload = await _json_object(request)
    if isinstance(payload, JSONResponse):
        return payload
    try:
        save_request = parse_save_request(payload)
        result = await run_in_threadpool(_deps(request).service.save, save_request)
    except MarkupError as exc:
        return _error(str(exc))
    return JSONResponse({'ok': True, **result.as_dict()}, headers=_NO_STORE)


@markup_lab_router.post('/api/open-file')
async def open_markup_file(request: Request) -> JSONResponse:
    """ Открывает JSON разметки видео в программе по умолчанию на этом компьютере. """
    payload = await _json_object(request)
    if isinstance(payload, JSONResponse):
        return payload
    try:
        variant = MarkupVariant(payload.get('variant'))
    except ValueError:
        return _error('Unknown markup variant')
    video, jsons_dir = payload.get('video'), payload.get('jsons_dir') or ''
    key = payload.get('production_key') or None
    if not isinstance(video, str) or not isinstance(jsons_dir, str) or not isinstance(key, (str, type(None))):
        return _error('Fields "video", "jsons_dir" and "production_key" must be strings')
    try:
        path = await run_in_threadpool(_deps(request).service.open_file, video, variant, jsons_dir, key)
    except MarkupError as exc:
        return _error(str(exc))
    return JSONResponse({'ok': True, 'path': str(path)}, headers=_NO_STORE)


@markup_lab_router.post('/api/open-video')
async def open_video_file(request: Request) -> JSONResponse:
    """ Открывает видеофайл в программе по умолчанию на этом компьютере. """
    payload = await _json_object(request)
    if isinstance(payload, JSONResponse):
        return payload
    video = payload.get('video')
    if not isinstance(video, str):
        return _error('Field "video" must be a string')
    try:
        path = await run_in_threadpool(_deps(request).service.open_video, video)
    except MarkupError as exc:
        return _error(str(exc))
    return JSONResponse({'ok': True, 'path': str(path)}, headers=_NO_STORE)


@markup_lab_router.post('/api/pick')
async def pick_path(request: Request) -> JSONResponse:
    """ Системное окно выбора каталога (``kind: dir``) или JSON (``kind: json``); отмена — ``path: null``. """
    payload = await _json_object(request)
    if isinstance(payload, JSONResponse):
        return payload
    initial = payload.get('initial') or ''
    if not isinstance(initial, str):
        return _error('Field "initial" must be a string')
    try:
        kind = PickKind(payload.get('kind') or PickKind.DIR.value)
    except ValueError:
        return _error('Unknown pick kind')
    try:
        path = await run_in_threadpool(_deps(request).path_picker, kind, initial)
    except PathPickerError as exc:
        return _error(str(exc), status=503)
    return JSONResponse({'ok': True, 'path': path}, headers=_NO_STORE)


@markup_lab_router.get('/frame')
def video_frame(request: Request) -> Response:
    """ Первый кадр видео в JPEG: ``full=1`` — для редактора, иначе — для карточки. """
    max_width = FULL_WIDTH if _param(request, 'full') else PREVIEW_WIDTH
    data = first_frame_jpeg(Path(_param(request, 'video')), max_width=max_width)
    if data is None:
        return Response(status_code=404)
    return Response(content=data, media_type='image/jpeg', headers=_NO_STORE)
