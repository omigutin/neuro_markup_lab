""" Ошибка окна выбора каталога или файла. """

__all__ = ['PathPickerError']


class PathPickerError(RuntimeError):
    """ Окно выбора недоступно (нет tkinter, нет графической среды) или упало. """
