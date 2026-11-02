""" Командная строка nml. """

import pytest

from neuro_markup_lab.cli import main
from neuro_markup_lab.cli.main import _DEFAULT_PORT, build_parser
from neuro_markup_lab.web import DEFAULT_PORT


def test_web_defaults():
    args = build_parser().parse_args(['web'])
    assert (args.host, args.port, args.no_browser) == ('127.0.0.1', DEFAULT_PORT, False)


def test_default_port_matches_web():
    assert _DEFAULT_PORT == DEFAULT_PORT


def test_command_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_web_passes_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr('neuro_markup_lab.web.run', lambda **kw: calls.append(kw))
    assert main(['web', '--port', '9100', '--no-browser']) == 0
    assert calls == [{'host': '127.0.0.1', 'port': 9100, 'open_browser': False}]
