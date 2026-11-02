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

## Боевая разметка видео

Боевая разметка — файл `<каталог JSON>/<ключ>.json`. Ключ выбирается так:

1. файл, выбранный пользователем для этого видео вручную;
2. ключ от приложения-хозяина (`MarkupLabHost.markup_key`);
3. подбор по файлам каталога: ключ и путь к видео делятся на блоки по `/ \ - _ . пробел`, файл подходит,
   если все его блоки есть в имени видео или в папках. `…/norebo/…/ml_cam25_2209.avi` → `norebo_cam25.json`.
   При нескольких подходящих побеждает файл, у которого больше блоков в имени видео, затем более длинный ключ,
   затем более близкие папки, затем производство видео. Равные кандидаты — выбирать вручную.

## Данные от приложения-хозяина

```python
from neuro_markup_lab import MarkupLabHost

class Host(MarkupLabHost):
    def markup_key(self, video):      # ключ боевой разметки; None — подобрать по каталогу
        return my_parser(video)
    def factories(self):              # известные производства
        return db.factories()
```

Всё необязательно: переопределяется только то, что хозяин знает. Методы вызываются на каждый запрос.
Новые данные добавляются новыми методами со значением «не знаю» по умолчанию.

## Запуск

```bash
nml web                                   # своя страница в браузере, порт 8790
nml web --port 8791 --no-browser
python run.py                             # то же из папки проекта, без установки
```

Если редактор уже запущен, команда открывает его в браузере; если порт занят другой программой — берёт следующий.

## Встраивание в другое веб-приложение

```python
from neuro_markup_lab.web import mount_app

mount_app(app, "/neuro-markup-lab",
          host=Host(),                                   # данные приложения-хозяина
          nav_renderer=lambda: render_nav("markup"))     # навигация приложения над страницей
```

Страница — `/neuro-markup-lab/`, все адреса на ней относительные, поэтому префикс любой.
`create_app(...)` возвращает то же приложение без встраивания.

## Кадр с разметкой и редактор в чужой странице

```html
<link rel="stylesheet" href="/neuro-markup-lab/static/neuro_markup_lab.css">
<script src="/neuro-markup-lab/static/neuro_markup_lab_shapes.js"></script>
<script src="/neuro-markup-lab/static/neuro_markup_lab_editor.js"></script>
<script src="/neuro-markup-lab/static/neuro_markup_lab_frame.js"></script>
```

Кадр с разметкой, переключателем «Боевая | Рядом с видео» и карандашом редактора — в любой элемент:

```js
const frame = NML.frame.mount(document.getElementById("slot"), {
  video: "D:/video/plant_cam5.avi",   // путь к видео на компьютере сервера
  jsonsDir: "D:/markup/plant",         // каталог боевых JSON; нет — только «рядом с видео»
  productionKey: null,                 // боевая, выбранная вручную; нет — подбирается
  details: true,                       // панель справа: файлы разметки, выбор боевой вручную, сведения
  onProductionKey: (key) => {},        // запомнить выбор вручную (страница редактора хранит его в браузере)
  onSaved: (variant, location) => {},
});
```

Только редактор, без кадра:

```js
NML.editor.open({ video, jsonsDir, variant, productionKey, urls, onSaved });
document.addEventListener("nml:saved", (e) => console.log(e.detail));  // {video, variant, location}
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
