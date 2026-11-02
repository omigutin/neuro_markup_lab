""" Первый кадр и размер кадра видео. """

import pytest

from neuro_markup_lab.videos import first_frame_jpeg, frame_size

cv2 = pytest.importorskip('cv2')
np = pytest.importorskip('numpy')

# Размер тестового видео, px
WIDTH, HEIGHT = 320, 240


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'clip.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 5, (WIDTH, HEIGHT))
    if not writer.isOpened():
        pytest.skip('OpenCV cannot write test video')
    for _ in range(3):
        writer.write(np.full((HEIGHT, WIDTH, 3), 120, dtype=np.uint8))
    writer.release()
    return path


def test_first_frame_is_jpeg_and_downscaled(video):
    data = first_frame_jpeg(video, max_width=160)
    assert data and data[:2] == b'\xff\xd8'
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[1] == 160 and image.shape[0] == 120


def test_first_frame_not_upscaled(video):
    image = cv2.imdecode(np.frombuffer(first_frame_jpeg(video, max_width=4000), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[1] == WIDTH


def test_frame_size(video):
    assert frame_size(video) == (WIDTH, HEIGHT)


def test_missing_or_not_video(tmp_path):
    bad = tmp_path / 'clip.avi'
    bad.write_bytes(b'garbage')
    assert first_frame_jpeg(tmp_path / 'none.avi') is None
    assert first_frame_jpeg(bad) is None
    assert first_frame_jpeg(tmp_path) is None
    assert frame_size(tmp_path / 'none.avi') is None
