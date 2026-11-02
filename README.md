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

## Запуск

```bash
nml web                                   # своя страница в браузере, порт 8790
nml web --port 8791 --no-browser
nml web --factory plant --factory mill    # фабрика видео ищется в пути по списку
python run.py                             # то же из папки проекта, без установки
```

Если редактор уже запущен, команда открывает его в браузере; если порт занят другой программой — берёт следующий.

## Встраивание в другое веб-приложение

```python
from neuro_markup_lab import MarkupLabService
from neuro_markup_lab.web import mount_app

mount_app(app, "/neuro-markup-lab",
          MarkupLabService(camera_resolver=camera_of),   # своя функция «видео → камера»
          nav_renderer=lambda: render_nav("markup"))     # навигация приложения над страницей
```

Страница — `/neuro-markup-lab/`, все адреса на ней относительные, поэтому префикс любой.
`create_app(...)` возвращает то же приложение без встраивания.

## Редактор в чужой странице

```html
<link rel="stylesheet" href="/neuro-markup-lab/static/neuro_markup_lab.css">
<script src="/neuro-markup-lab/static/neuro_markup_lab_shapes.js"></script>
<script src="/neuro-markup-lab/static/neuro_markup_lab_editor.js"></script>
<script>
  NML.editor.open({
    video: "D:/video/plant_cam5.avi",   // путь к видео на компьютере сервера
    jsonsDir: "D:/markup/plant",         // каталог боевых JSON; нет — только «рядом с видео»
    variant: "sidecar",                  // необязательно: по умолчанию «рядом с видео», если есть
    urls: {},                            // необязательно: свои адреса markup, save, frame, locations
    onSaved: (variant, location) => {},
  });
  document.addEventListener("nml:saved", (e) => console.log(e.detail));  // {video, variant, location}
</script>
```

Окно редактора вставляется в страницу при первом открытии. Адрес API берётся из адреса скрипта;
если скрипты собраны в один файл, задайте его сами: `window.NML_BASE = "/neuro-markup-lab/"`.

## Разработка

```bash
poetry install --all-extras
poetry run ruff check .
poetry run mypy
poetry run pytest
```
