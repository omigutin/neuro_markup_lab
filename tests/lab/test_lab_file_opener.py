""" Открытие файла программой по умолчанию. """

import pytest

from neuro_markup_lab.lab import SystemFileOpener, lab_file_opener
from neuro_markup_lab.markup import MarkupError


def test_linux_uses_xdg_open(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(lab_file_opener.sys, 'platform', 'linux')
    monkeypatch.setattr(lab_file_opener.subprocess, 'Popen', lambda args, **kw: calls.append(args))
    SystemFileOpener().open(tmp_path / 'a.json')
    assert calls == [['xdg-open', str(tmp_path / 'a.json')]]


def test_windows_uses_startfile(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(lab_file_opener.sys, 'platform', 'win32')
    monkeypatch.setattr(lab_file_opener.os, 'startfile', calls.append, raising=False)
    SystemFileOpener().open(tmp_path / 'a.json')
    assert calls == [str(tmp_path / 'a.json')]


def test_error_becomes_markup_error(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise OSError('no app')
    monkeypatch.setattr(lab_file_opener.sys, 'platform', 'linux')
    monkeypatch.setattr(lab_file_opener.subprocess, 'Popen', fail)
    with pytest.raises(MarkupError):
        SystemFileOpener().open(tmp_path / 'a.json')
