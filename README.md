# neuro_markup_lab

Редактор разметки зон (LabelMe-json) по кадру видео: источники разметки «рядом с видео» и «боевая»,
схема и приведение типов атрибутов, версии разметки, веб-интерфейс.

Библиотекой можно пользоваться без веб-интерфейса: базовая установка не тянет fastapi.

## Установка

```bash
pip install neuro-markup-lab               # только библиотека
pip install "neuro-markup-lab[web]"        # с веб-интерфейсом
pip install "neuro-markup-lab[headless]"   # кадр видео через opencv-python-headless
```

Если в проекте-хозяине уже стоит `opencv-python`, части `opencv`/`headless` не ставьте.

## Формат разметки

```python
from neuro_markup_lab import MarkupDocument, ShapeLabel

document = MarkupDocument.model_validate_json(path.read_text(encoding="utf-8"))
for shape in document.shapes:
    if shape.label is ShapeLabel.WORK_ZONE:
        speed = shape.attribute("speed_limit")   # поле, добавленное в редакторе; нет — None
```

- Известные поля фигуры описаны в `MarkupShape`: тип, подпись и подсказка редактора. Схема редактора строится из модели.
- Поля, добавленные в редакторе, сохраняются в JSON и читаются по имени через `MarkupShape.attribute`.
- Новое постоянное поле добавляется в `MarkupShape` и выходит новой версией библиотеки.

## Камера видео и боевая разметка

Боевая разметка камеры — `<каталог JSON>/<factory>_cam<N>.json`. Камеру по пути видео определяет `CameraResolver`:
по умолчанию `CameraNameParser` (`plant_cam5_x.avi` → `plant`, `5`; со списком фабрик — фабрика из пути).
Приложение может передать свою функцию: `MarkupLabService(camera_resolver=...)`.

## Разработка

```bash
poetry install --all-extras
poetry run ruff check .
poetry run mypy
poetry run pytest
```
