""" Подбор боевой разметки видео по каталогу JSON (правила — docs/markup_selection.md). """

from pathlib import Path

import pytest

from neuro_markup_lab.storage import KeyMatch, find_factory, match_markup_key, split_blocks

# Каталог боевых JSON одного производства: ключи файлов
SITE = ['site_a_cam2', 'site_a_cam25', 'site_a_cam26', 'site_a_cam3']
# Видео, у которого производство — в папке, а в имени перед cam — другая часть
VIDEO = Path('D:/archive/site_a/raw/VIDEO/site_a/Партия/ml_cam25_22092026_1310.avi')


def test_split_blocks():
    assert split_blocks('ML_cam25-2209.x y') == ['ml', 'cam25', '2209', 'x', 'y']


def test_parts_in_folder_and_name():
    assert match_markup_key(VIDEO, SITE) == KeyMatch('site_a_cam25')


def test_parts_compared_whole():
    assert match_markup_key(Path('/v/site_a/ml_cam2_x.avi'), SITE).key == 'site_a_cam2'


def test_no_match():
    assert match_markup_key(Path('/v/other/ml_cam25.avi'), SITE) == KeyMatch(None)


def test_name_beats_folder():
    # site есть и в имени видео, и в папке; файл, у которого больше частей в имени видео, побеждает
    keys = ['site_cam25', 'line_cam25']
    assert match_markup_key(Path('/line/site_cam25_x.avi'), keys).key == 'site_cam25'


def test_docs_example():
    video = Path('D:/video/site_a/day1/line1_cam25_0101_1310.avi')
    keys = ['site_a_cam25', 'site_a_cam2', 'line1_cam25', 'site_b_cam25']
    assert match_markup_key(video, keys).key == 'line1_cam25'
    assert match_markup_key(video, ['site_a_cam25', 'site_a_cam2', 'site_b_cam25']).key == 'site_a_cam25'


def test_longer_key_wins():
    assert match_markup_key(Path('/site/cam25.avi'), ['cam25', 'site_cam25']).key == 'site_cam25'


def test_nearer_folder_wins():
    assert match_markup_key(Path('/a/b/cam1.avi'), ['a_cam1', 'b_cam1']).key == 'b_cam1'


def test_ambiguous_returns_candidates():
    assert match_markup_key(Path('/x_y/cam1.avi'), ['x_cam1', 'y_cam1']) == KeyMatch(None, ('x_cam1', 'y_cam1'))


def test_factory_breaks_tie():
    assert match_markup_key(Path('/x_y/cam1.avi'), ['x_cam1', 'y_cam1'], factories=['y']).key == 'y_cam1'


def test_other_naming_without_settings():
    assert match_markup_key(Path('/line1/top_2026.avi'), ['line1_top', 'line1_bottom']).key == 'line1_top'


@pytest.mark.parametrize(('path', 'expected'), [
    (VIDEO, 'Site_a'),
    (Path('/plant/mill_cam3.avi'), 'mill'),
    (Path('/x/cam3.avi'), None),
])
def test_find_factory(path, expected):
    # Производство ищется сначала в имени видео, затем в папках; написание — как у хозяина
    assert find_factory(path, ['Site_a', 'plant', 'mill']) == expected
