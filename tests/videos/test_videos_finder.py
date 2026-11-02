""" Поиск видео в каталоге. """

from neuro_markup_lab.videos import VideoFinder


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'x')
    return path


def test_flat_search(tmp_path):
    for name in ('b.mp4', 'A.AVI', 'note.txt', 'sub/c.mp4'):
        touch(tmp_path / name)
    found = VideoFinder().find(tmp_path, recursive=False, warnings=[])
    assert [f.path.name for f in found] == ['A.AVI', 'b.mp4']
    assert all(f.relative_dir == '' for f in found)


def test_recursive_skips_runs_and_hidden_keeps_duplicates(tmp_path):
    touch(tmp_path / 'x.mp4')
    touch(tmp_path / 'day1' / 'x.mp4')
    touch(tmp_path / 'day1' / 'a.mp4')
    touch(tmp_path / 'day1' / 'deep' / 'y.mkv')
    touch(tmp_path / 'runs' / 'r1' / 'x.mp4')
    touch(tmp_path / '.cache' / 'z.mp4')
    found = VideoFinder().find(tmp_path, recursive=True, warnings=[])
    # Видео одного подкаталога идут подряд; одинаковые имена в разных подкаталогах остаются
    assert [(f.relative_dir, f.path.name) for f in found] == [
        ('', 'x.mp4'), ('day1', 'a.mp4'), ('day1', 'x.mp4'), ('day1/deep', 'y.mkv')]
