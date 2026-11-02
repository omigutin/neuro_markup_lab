""" Окно выбора каталога или файла: разбор ответа процесса с окном. """

import subprocess

import pytest

from neuro_markup_lab.web import PathPickerError, PickKind, web_path_picker


def _fake_run(returncode: int, stdout: bytes = b'', stderr: bytes = b''):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)
    return run


def test_selected_folder(monkeypatch):
    monkeypatch.setattr(web_path_picker.subprocess, 'run', _fake_run(0, 'D:/видео'.encode()))
    assert web_path_picker.pick_path(PickKind.DIR, '') == 'D:/видео'


def test_cancelled(monkeypatch):
    monkeypatch.setattr(web_path_picker.subprocess, 'run', _fake_run(0, b''))
    assert web_path_picker.pick_path(PickKind.JSON, 'D:/') is None


def test_not_available(monkeypatch):
    monkeypatch.setattr(web_path_picker.subprocess, 'run', _fake_run(1, stderr=b"No module named 'tkinter'"))
    with pytest.raises(PathPickerError, match='tkinter'):
        web_path_picker.pick_path(PickKind.DIR, '')
