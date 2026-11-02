""" Версии разметки рядом с видео. """

import json
from pathlib import Path

import pytest

from neuro_markup_lab.markup import MarkupError
from neuro_markup_lab.storage import SaveMode, VersionOrigin, VersionStore, file_hash

from ..conftest import make_document


def doc(x: float) -> dict:
    return make_document([{'label': 'crop', 'points': [[x, 0], [x + 1, 1]], 'shape_type': 'rectangle'}])


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    video = tmp_path / 'videos' / 'line1_cam5.avi'
    video.parent.mkdir()
    video.write_bytes(b'x')
    return VersionStore(video)


def test_paths(store, tmp_path):
    assert store.working_path == tmp_path / 'videos' / 'line1_cam5.markup.json'
    assert store.directory == tmp_path / 'videos' / 'line1_cam5_jsons'


def test_empty_history(store):
    history = store.history()
    assert history.versions == [] and history.current is None
    assert store.working_matches_current()


def test_new_versions_become_current(store):
    v1 = store.save(doc(1), SaveMode.NEW_VERSION, source='production', comment='первая')
    v2 = store.save(doc(2), SaveMode.NEW_VERSION, base_version=1, source='sidecar')
    history = store.history()
    assert [v.number for v in history.versions] == [1, 2] and history.current == 2
    assert v1.origin == VersionOrigin.EDITOR and v1.comment == 'первая' and v2.based_on == 1
    assert json.loads(store.working_path.read_text(encoding='utf-8')) == doc(2)
    assert store.load(1) == doc(1)
    assert file_hash(store.working_path) == history.current_version.hash
    assert (store.directory / v1.file).is_file() and v1.file.startswith('v1_')


def test_overwrite_open_version(store):
    store.save(doc(1), SaveMode.NEW_VERSION)
    store.save(doc(2), SaveMode.NEW_VERSION)
    version = store.save(doc(3), SaveMode.OVERWRITE, base_version=1)
    history = store.history()
    assert version.number == 1 and len(history.versions) == 2 and history.current == 1
    assert store.load(1) == doc(3) and json.loads(store.working_path.read_text(encoding='utf-8')) == doc(3)
    with pytest.raises(MarkupError):
        store.save(doc(4), SaveMode.OVERWRITE, base_version=9)


def test_existing_file_saved_as_initial(store):
    store.working_path.write_text(json.dumps(doc(7)), encoding='utf-8')
    store.save(doc(8), SaveMode.NEW_VERSION)
    history = store.history()
    assert [v.origin for v in history.versions] == [VersionOrigin.INITIAL, VersionOrigin.EDITOR]
    assert store.load(1) == doc(7) and history.current == 2


def test_external_change_is_kept(store):
    store.save(doc(1), SaveMode.NEW_VERSION)
    store.working_path.write_text(json.dumps(doc(5)), encoding='utf-8')
    assert not store.working_matches_current()
    store.save(doc(6), SaveMode.OVERWRITE, base_version=1)
    history = store.history()
    assert [v.origin for v in history.versions] == [VersionOrigin.EDITOR, VersionOrigin.EXTERNAL]
    assert store.load(2) == doc(5) and store.load(1) == doc(6) and history.current == 1


def test_make_current(store):
    store.save(doc(1), SaveMode.NEW_VERSION)
    store.save(doc(2), SaveMode.NEW_VERSION)
    store.make_current(1)
    assert store.history().current == 1 and json.loads(store.working_path.read_text(encoding='utf-8')) == doc(1)
    assert store.working_matches_current()
    with pytest.raises(MarkupError):
        store.make_current(5)


def test_update_pin_and_comment(store):
    store.save(doc(1), SaveMode.NEW_VERSION)
    store.update(1, pinned=True, comment='эталон')
    version = store.history().get(1)
    assert version.pinned and version.comment == 'эталон'
    store.update(1, pinned=False)
    assert not store.history().get(1).pinned and store.history().get(1).comment == 'эталон'


def test_many_versions(store):
    for i in range(30):
        store.save(doc(i), SaveMode.NEW_VERSION)
    history = store.history()
    assert len(history.versions) == 30 and history.current == 30 and store.load(15) == doc(14)


def test_broken_index(store):
    store.directory.mkdir()
    (store.directory / 'versions.json').write_text('{', encoding='utf-8')
    with pytest.raises(MarkupError):
        store.history()
