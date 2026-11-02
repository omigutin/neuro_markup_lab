""" Ошибка окна выбора каталога. """

__all__ = ['FolderPickerError']


class FolderPickerError(RuntimeError):
    """ Окно выбора каталога недоступно (нет tkinter, нет графической среды) или упало. """
