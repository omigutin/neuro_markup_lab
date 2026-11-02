""" Отдельный запуск: выбор порта. """

import socket

from neuro_markup_lab.web import find_port, web_server


def test_free_port_is_used():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    assert find_port('127.0.0.1', port) == (port, False)


def test_busy_port_skipped(monkeypatch):
    monkeypatch.setattr(web_server, '_port_free', lambda host, port: port != 9000)
    monkeypatch.setattr(web_server, '_is_markup_lab', lambda host, port: False)
    assert find_port('127.0.0.1', 9000) == (9001, False)


def test_running_markup_lab_detected(monkeypatch):
    monkeypatch.setattr(web_server, '_port_free', lambda host, port: False)
    monkeypatch.setattr(web_server, '_is_markup_lab', lambda host, port: port == 9002)
    assert find_port('127.0.0.1', 9000) == (9002, True)
