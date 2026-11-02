""" Окно выбора каталога: разбор ответа процесса с окном. """

import subprocess

import pytest

from neuro_markup_lab.web import FolderPickerError, web_folder_picker


def _fake_run(returncode: int, stdout: bytes = b'', stderr: bytes = b''):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)
    return run


def test_selected_folder(monkeypatch):
    monkeypatch.setattr(web_folder_picker.subprocess, 'run', _fake_run(0, 'D:/видео'.encode()))
    assert web_folder_picker.pick_folder('') == 'D:/видео'


def test_cancelled(monkeypatch):
    monkeypatch.setattr(web_folder_picker.subprocess, 'run', _fake_run(0, b''))
    assert web_folder_picker.pick_folder('D:/') is None


def test_not_available(monkeypatch):
    monkeypatch.setattr(web_folder_picker.subprocess, 'run', _fake_run(1, stderr=b"No module named 'tkinter'"))
    with pytest.raises(FolderPickerError, match='tkinter'):
        web_folder_picker.pick_folder('')
