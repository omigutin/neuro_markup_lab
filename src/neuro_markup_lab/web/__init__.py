""" Web-слой NeuroMarkupLab: страница разметки и её API, подключаются к хосту через :func:`mount`. """

__all__ = ['NeuroMarkupLabWebDependencies', 'build_web_dependencies', 'mount']

from .web_module import build_web_dependencies, mount
from .web_types import NeuroMarkupLabWebDependencies
