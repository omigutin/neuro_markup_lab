""" Статика без кэширования браузером: правки JS/CSS видны без сброса кэша. """

__all__ = ['NoCacheStaticFiles']

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class NoCacheStaticFiles(StaticFiles):
    """ Отдаёт файлы с ``Cache-Control: no-store``. """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-store'
        return response
