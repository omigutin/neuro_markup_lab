""" Подбор боевой разметки видео по каталогу JSON. """

from pathlib import Path

import pytest

from neuro_markup_lab.storage import KeyMatch, find_factory, match_markup_key, split_blocks

# Каталог боевых JSON производства: ключи файлов
NOREBO = ['norebo_cam2', 'norebo_cam25', 'norebo_cam26', 'norebo_cam3']
# Видео, у которого производство — в папке, а перед cam — модуль
VIDEO = Path('W:/Projects/_VIDEO_/norebo/ms/VIDEO/norebo/Зубатка/ml_cam25_22092026_1310.avi')


def test_split_blocks():
    assert split_blocks('ML_cam25-2209.x y') == ['ml', 'cam25', '2209', 'x', 'y']


def test_factory_in_folder_cam_in_name():
    assert match_markup_key(VIDEO, NOREBO) == KeyMatch('norebo_cam25')


def test_blocks_compared_whole():
    assert match_markup_key(Path('/v/norebo/ml_cam2_x.avi'), NOREBO).key == 'norebo_cam2'


def test_no_match():
    assert match_markup_key(Path('/v/other/ml_cam25.avi'), NOREBO) == KeyMatch(None)


def test_name_beats_folder():
    # norebo есть и в имени, и в папке; ключ, у которого больше блоков в имени, побеждает
    keys = ['norebo_cam25', 'line_cam25']
    video = Path('/line/norebo_cam25_x.avi')
    assert match_markup_key(video, keys).key == 'norebo_cam25'


def test_longer_key_wins():
    assert match_markup_key(Path('/norebo/cam25.avi'), ['cam25', 'norebo_cam25']).key == 'norebo_cam25'


def test_nearer_folder_wins():
    keys = ['a_cam1', 'b_cam1']
    assert match_markup_key(Path('/a/b/cam1.avi'), keys).key == 'b_cam1'


def test_ambiguous_returns_candidates():
    keys = ['x_cam1', 'y_cam1']
    assert match_markup_key(Path('/x_y/cam1.avi'), keys) == KeyMatch(None, ('x_cam1', 'y_cam1'))


def test_factory_breaks_tie():
    keys = ['x_cam1', 'y_cam1']
    assert match_markup_key(Path('/x_y/cam1.avi'), keys, factories=['y']).key == 'y_cam1'


def test_other_naming_without_settings():
    assert match_markup_key(Path('/line1/top_2026.avi'), ['line1_top', 'line1_bottom']).key == 'line1_top'


@pytest.mark.parametrize(('path', 'expected'), [
    (VIDEO, 'norebo'),
    (Path('/plant/mill_cam3.avi'), 'mill'),
    (Path('/x/cam3.avi'), None),
])
def test_find_factory(path, expected):
    assert find_factory(path, ['Norebo', 'plant', 'mill']) in (expected, expected and expected.capitalize())


def test_find_factory_keeps_host_spelling():
    assert find_factory(VIDEO, ['Norebo']) == 'Norebo'
