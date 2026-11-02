""" Типы пакета markup: перечисления формата, типы атрибутов, описание поля, приведение типов, правка фигуры. """

__all__ = [
    'DEFAULT_FILL_COLOR',
    'DEFAULT_IMAGE_HEIGHT',
    'DEFAULT_IMAGE_PATH',
    'DEFAULT_IMAGE_WIDTH',
    'DEFAULT_LINE_COLOR',
    'FIXED_POINTS_SHAPE_TYPES',
    'LABELME_VERSION',
    'SHAPE_RESERVED_KEYS',
    'SHAPE_TYPE_MIN_POINTS',
    'AttributeSpec',
    'AttributeType',
    'EditorField',
    'JsonValue',
    'NormalizationReport',
    'RgbaColor',
    'ShapeChange',
    'ShapeLabel',
    'ShapePosition',
    'ShapeType',
    'ValueConversion',
    'ValueProblem',
]

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

# Значение из JSON (рекурсивно)
JsonValue: TypeAlias = bool | int | float | str | list['JsonValue'] | dict[str, 'JsonValue'] | None

# Цвет LabelMe: (R, G, B, A)
RgbaColor: TypeAlias = tuple[int, int, int, int]

# Значения полей документа LabelMe по умолчанию
LABELME_VERSION = '5.5.0'
DEFAULT_IMAGE_PATH = 'cam.jpg'
DEFAULT_IMAGE_WIDTH = 1920
DEFAULT_IMAGE_HEIGHT = 1080
DEFAULT_LINE_COLOR: RgbaColor = (0, 255, 0, 128)
DEFAULT_FILL_COLOR: RgbaColor = (255, 0, 0, 128)

# Ключи фигуры, которые не являются атрибутами: геометрию правит сцена редактора
SHAPE_RESERVED_KEYS: frozenset[str] = frozenset({'points', 'shape_type'})

# Допустимые типы фигур и минимальное число точек для каждого (как в LabelMe)
SHAPE_TYPE_MIN_POINTS: dict[str, int] = {
    'polygon': 3,
    'rectangle': 2,
    'line': 2,
    'linestrip': 2,
    'circle': 2,
    'point': 1,
}
# Типы фигур, у которых точек ровно минимум (прямоугольник — 2 угла, линия — 2 конца и т.п.)
FIXED_POINTS_SHAPE_TYPES: frozenset[str] = frozenset({'rectangle', 'line', 'circle', 'point'})


class ShapeLabel(str, Enum):
    """ Метка фигуры: её роль в разметке. """
    NONE = ''
    PROMT = 'promt'            # устарела, не используется
    CROP = 'crop'              # вырезка кадра для нейросети
    SEARCH = 'search'          # устарела, не используется
    INPUT = 'input'            # линия входа продукта
    OUTPUT = 'output'          # линия выхода продукта
    WORK_ZONE = 'work_zone'    # рабочая зона: место работы человека
    AUTOMARKUP = 'automarkup'  # область поиска рабочей поверхности для авторазметки


class ShapePosition(str, Enum):
    """ Положение фигуры относительно рабочего места. """
    NONE = ''
    LEFT = 'left'
    RIGHT = 'right'
    TOP = 'top'
    BOTTOM = 'bottom'
    CENTRE = 'centre'


class ShapeType(str, Enum):
    """ Тип фигуры LabelMe. """
    NONE = ''
    LINE = 'line'
    POINT = 'point'
    POLYGON = 'polygon'
    RECTANGLE = 'rectangle'


@dataclass(frozen=True, slots=True)
class EditorField:
    """
        Как показывать поле модели фигуры в редакторе. Ставится в ``Annotated`` у поля
        :class:`MarkupShape`; подпись и подсказка берутся из ``Field(title=..., description=...)``.
    """
    # Порядок показа в редакторе (меньше — выше)
    order: int
    # Нельзя удалить у фигуры
    required: bool = False
    # Значения перечисления, которые устарели (помечаются в редакторе)
    deprecated: tuple[Enum, ...] = ()
    # Значения перечисления, которые нельзя выбрать
    excluded: tuple[Enum, ...] = ()
    # Не показывать в редакторе (значение в JSON сохраняется как есть)
    hidden: bool = False


class AttributeType(str, Enum):
    """ Тип значения атрибута фигуры. Значение стабильно — уходит в UI и в запросы. """
    INT = 'int'
    FLOAT = 'float'
    STR = 'str'
    BOOL = 'bool'
    DICT = 'dict'
    ANY = 'any'        # значение не проверяется и не правится (например, mask)


@dataclass(frozen=True, slots=True)
class AttributeSpec:
    """ Описание атрибута фигуры: тип, допустимость null и подсказки для редактора. """
    # Имя ключа в JSON фигуры
    name: str
    # Тип значения, к которому приводятся все фигуры документа
    type: AttributeType
    # Можно ли хранить null
    nullable: bool
    # Поле модели фигуры (тип задан моделью и не меняется) или поле документа
    known: bool = False
    # Нельзя удалить у фигуры (например, label)
    required: bool = False
    # Допустимые значения (для strict) или подсказки значений
    choices: tuple[str, ...] = ()
    # Значение обязано быть из choices: модель читает поле как перечисление и не примет другое значение
    strict: bool = False
    # Значения из choices, которые код больше не использует (помечаются в редакторе)
    deprecated: tuple[str, ...] = ()
    # Подпись поля в редакторе
    title: str = ''
    # Где и как используется поле (подсказка в редакторе)
    hint: str = ''
    # Не показывать в редакторе (значение в JSON сохраняется как есть)
    hidden: bool = False

    @property
    def expected(self) -> str:
        """ Ожидаемое значение в читаемом виде: ``int | null`` или список допустимых значений. """
        if self.strict:
            return ' | '.join(repr(c) for c in self.choices)
        return f'{self.type.value} | null' if self.nullable else self.type.value

    def accepts(self, value: JsonValue) -> bool:
        """ Значение входит в допустимые (для strict); остальные поля принимают любое значение типа. """
        return not self.strict or value in self.choices

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            'name': self.name, 'type': self.type.value, 'nullable': self.nullable, 'known': self.known,
            'required': self.required, 'choices': list(self.choices), 'strict': self.strict,
            'deprecated': list(self.deprecated), 'title': self.title, 'hint': self.hint, 'hidden': self.hidden,
        }


@dataclass(frozen=True, slots=True)
class ValueConversion:
    """ Значение атрибута, которое будет приведено к типу поля. """
    shape_index: int
    label: str
    field: str
    before: JsonValue
    after: JsonValue

    def as_dict(self) -> dict[str, JsonValue]:
        return {'shape_index': self.shape_index, 'label': self.label, 'field': self.field,
                'before': self.before, 'after': self.after}


@dataclass(frozen=True, slots=True)
class ValueProblem:
    """ Значение атрибута, которое нельзя привести к типу поля автоматически. """
    shape_index: int
    label: str
    field: str
    value: JsonValue
    expected: str

    def as_dict(self) -> dict[str, JsonValue]:
        return {'shape_index': self.shape_index, 'label': self.label, 'field': self.field,
                'value': self.value, 'expected': self.expected}


@dataclass(slots=True)
class NormalizationReport:
    """ Итог приведения типов документа: что приведено и что требует ручной правки. """
    conversions: list[ValueConversion] = field(default_factory=list)
    problems: list[ValueProblem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """ Документ можно сохранить: проблем, требующих ручной правки, нет. """
        return not self.problems

    def as_dict(self) -> dict[str, JsonValue]:
        return {'conversions': [c.as_dict() for c in self.conversions],
                'problems': [p.as_dict() for p in self.problems]}


@dataclass(frozen=True, slots=True)
class ShapeChange:
    """
        Правка одной фигуры из редактора. ``None`` — поле не менялось.
        ``attributes`` — полный желаемый набор атрибутов фигуры: отсутствующие в нём ключи удаляются.
    """
    # Точки как пришли из запроса: ``[[x, y], ...]``; структура проверяется при применении правки
    points: list[JsonValue] | None = None
    shape_type: str | None = None
    attributes: dict[str, JsonValue] | None = None
