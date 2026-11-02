""" Ошибка записи: файл разметки изменился после того, как его открыли в редакторе. """

__all__ = ['MarkupConflictError']

from ..markup import MarkupError


class MarkupConflictError(MarkupError):
    """ Файл разметки изменён после открытия; запись — только с явным подтверждением (``force``). """
