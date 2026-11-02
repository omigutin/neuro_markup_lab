"""
Фигура разметки LabelMe.

Известные поля типизированы; описание поля (подпись, подсказка, порядок в редакторе) задаётся
здесь же, и схема редактора строится из модели. Поля, которых нет в модели (добавленные
в редакторе), не теряются: читаются через :meth:`MarkupShape.attribute` и записываются обратно.
"""

__all__ = ['MarkupShape']

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from .markup_types import EditorField, ShapeLabel, ShapePosition, ShapeType

# Подсказка служебных полей LabelMe
_LABELME_FIELD_HINT = 'Служебное поле LabelMe.'


class MarkupShape(BaseModel):
    """ Фигура разметки: геометрия, известные поля и поля, добавленные в редакторе. """

    model_config = ConfigDict(extra='allow')

    wz: Annotated[int | None, EditorField(order=3)] = Field(
        None, title='Рабочая зона',
        description='Номер рабочей зоны, к которой относится фигура. Обязателен для фигур рабочих зон, подзон и '
                    'линий пересечения; совпадает с group_id одной из фигур рабочих зон.')
    markup: Annotated[int | None, EditorField(order=5)] = Field(
        None, title='Набор разметки',
        description='Номер набора разметки: камера берёт фигуры своего набора, например по виду продукции. '
                    'null — набор по умолчанию.')
    position: Annotated[ShapePosition, EditorField(order=4)] = Field(
        ShapePosition.NONE, title='Положение',
        description='Сторона рабочего места: направление подсчёта при пересечении линий и положение подписей '
                    'при отрисовке. Пусто — для зоны centre.')
    label: Annotated[ShapeLabel, EditorField(order=1, required=True, excluded=(ShapeLabel.NONE,),
                                             deprecated=(ShapeLabel.SEARCH, ShapeLabel.PROMT))] = Field(
        ShapeLabel.SEARCH, title='Метка',
        description='Роль фигуры: crop — вырезка для нейросети, input/output — линии подсчёта, work_zone — место '
                    'работника, automarkup — область поиска стола авторазметкой. Только из списка, иначе '
                    'разметку не прочитать.')
    # Точки фигуры в пикселях исходного кадра
    points: list[Any] = Field(default_factory=list)
    group_id: Annotated[int | None, EditorField(order=2)] = Field(
        None, title='Номер фигуры',
        description='Для фигуры рабочей зоны — номер рабочего места. Для подзоны или вырезки — номер подзоны '
                    'внутри рабочего места. null — общая фигура (только для вырезки).')
    description: Annotated[str | None, EditorField(order=7)] = Field(
        None, title='Описание', description=_LABELME_FIELD_HINT)
    # Тип фигуры: многоугольник, прямоугольник, линия, точка
    shape_type: ShapeType = ShapeType.POLYGON
    flags: Annotated[dict[str, Any], EditorField(order=8)] = Field(
        default_factory=dict, title='Флаги', description=_LABELME_FIELD_HINT)
    mask: Annotated[Any, EditorField(order=9, hidden=True)] = Field(
        None, title='Маска', description=_LABELME_FIELD_HINT)
    show: Annotated[bool, EditorField(order=6)] = Field(
        True, title='Показывать',
        description='Рисовать фигуру при отрисовке. false — не рисуется, но в логике (вырезка, зоны, '
                    'авторазметка) участвует. Нет поля — true.')

    def attribute(self, name: str, default: Any = None) -> Any:
        """ Значение поля по имени: известного или добавленного в редакторе; нет поля — ``default``. """
        if name in type(self).model_fields:
            return getattr(self, name)
        return (self.model_extra or {}).get(name, default)
