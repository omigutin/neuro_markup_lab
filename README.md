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

## Разработка

```bash
poetry install --all-extras
poetry run ruff check .
poetry run mypy
poetry run pytest
```
