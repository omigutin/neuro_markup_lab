""" Чтение и атомарная запись JSON. """

import pytest

from neuro_markup_lab.markup import MarkupError
from neuro_markup_lab.storage import file_hash, read_json_document, text_hash, write_json_document, write_json_text


def test_write_creates_dirs_and_no_tmp_left(tmp_path):
    path = tmp_path / 'a' / 'b.json'
    write_json_document(path, {'k': [1, 2], 'z': 'я'})
    assert read_json_document(path) == {'k': [1, 2], 'z': 'я'}
    assert [p.name for p in path.parent.iterdir()] == ['b.json']


def test_write_keeps_line_endings(tmp_path):
    path = tmp_path / 'x.json'
    write_json_text(path, '{\n  "a": 1\n}')
    assert path.read_bytes() == b'{\n  "a": 1\n}'
    assert file_hash(path) == text_hash('{\n  "a": 1\n}')


def test_hash_ignores_line_endings(tmp_path):
    path = tmp_path / 'x.json'
    path.write_bytes(b'{\r\n  "a": 1\r\n}')
    assert file_hash(path) == text_hash('{\n  "a": 1\n}')
    assert file_hash(path) != text_hash('{\n  "a": 2\n}')


def test_write_keeps_key_order(tmp_path):
    path = tmp_path / 'x.json'
    write_json_document(path, {'b': 1, 'a': 2})
    assert list(read_json_document(path)) == ['b', 'a']


@pytest.mark.parametrize('content', ['{bad', '[1, 2]'])
def test_read_invalid(tmp_path, content):
    path = tmp_path / 'x.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(MarkupError):
        read_json_document(path)


def test_read_missing(tmp_path):
    with pytest.raises(MarkupError):
        read_json_document(tmp_path / 'none.json')
