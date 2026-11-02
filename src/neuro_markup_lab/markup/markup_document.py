""" Документ разметки LabelMe: поля документа и фигуры. """

__all__ = ['MarkupDocument']

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .markup_shape import MarkupShape
from .markup_types import (
    DEFAULT_FILL_COLOR,
    DEFAULT_IMAGE_HEIGHT,
    DEFAULT_IMAGE_PATH,
    DEFAULT_IMAGE_WIDTH,
    DEFAULT_LINE_COLOR,
    LABELME_VERSION,
    RgbaColor,
)


class MarkupDocument(BaseModel):
    """ Документ разметки. Поля, которых нет в модели, сохраняются как есть. """

    model_config = ConfigDict(extra='allow')

    # Версия формата LabelMe
    version: str = LABELME_VERSION
    # Флаги документа LabelMe
    flags: dict[str, Any] = Field(default_factory=dict)
    # Фигуры разметки
    shapes: list[MarkupShape] = Field(default_factory=list)
    # Имя кадра, по которому сделана разметка
    imagePath: str = DEFAULT_IMAGE_PATH
    # Кадр в base64; обычно не хранится
    imageData: str | None = None
    # Размер кадра, к которому относятся координаты фигур, px
    imageHeight: int = DEFAULT_IMAGE_HEIGHT
    imageWidth: int = DEFAULT_IMAGE_WIDTH
    # Цвета линий и заливки LabelMe
    lineColor: RgbaColor = DEFAULT_LINE_COLOR
    fillColor: RgbaColor = DEFAULT_FILL_COLOR
