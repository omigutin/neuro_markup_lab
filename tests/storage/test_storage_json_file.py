""" Чтение и атомарная запись JSON. """

import pytest

from neuro_markup_lab.markup import MarkupError
from neuro_markup_lab.storage import read_json_document, write_json_document


def test_write_creates_dirs_and_no_tmp_left(tmp_path):
    path = tmp_path / 'a' / 'b.json'
    write_json_document(path, {'k': [1, 2], 'z': 'я'})
    assert read_json_document(path) == {'k': [1, 2], 'z': 'я'}
    assert [p.name for p in path.parent.iterdir()] == ['b.json']


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
