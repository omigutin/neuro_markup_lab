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

## Разметка видео

У видео два варианта разметки: **рядом с видео** (`<имя видео>.markup.json`) и **боевая**
(`<каталог боевых JSON>/<ключ>.json`). Ключ боевой выбирается так: выбран вручную → задан
приложением-хозяином → подобран по частям имени файла в имени и пути видео.

Полные правила с примерами — [docs/markup_selection.md](docs/markup_selection.md).

У разметки рядом с видео — история версий в `<папка видео>/<имя видео>_jsons/`: «Сохранить как новую версию»,
«Сохранить» (в открытую версию), выбор текущей версии. Боевая перезаписывается, прежняя копия — `.bak`.
Подробно — [docs/markup_versions.md](docs/markup_versions.md).

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
  video: "D:/video/line1_cam5.avi",   // путь к видео на компьютере сервера
  jsonsDir: "D:/markup",         // каталог боевых JSON; нет — только «рядом с видео»
  productionKey: null,                 // боевая, выбранная вручную; нет — подбирается
  details: true,                       // панель справа: файлы разметки, выбор боевой вручную, сведения
  variant: "sidecar",                  // что показать: "sidecar" | "production"; нет — выбирается само
  version: 3,                          // версия рядом с видео для показа; нет — текущая
  locked: false,                       // true — только этот вариант и версия, без переключения (просмотр)
  editable: true,                      // карандаш редактора
  onVariant: (variant) => {},          // сменился показываемый вариант
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
