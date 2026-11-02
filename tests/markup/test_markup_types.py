""" Типы пакета markup. """

from neuro_markup_lab.markup import AttributeSpec, AttributeType, NormalizationReport, ValueConversion, ValueProblem


def test_expected_text():
    assert AttributeSpec('wz', AttributeType.INT, nullable=True).expected == 'int | null'
    assert AttributeSpec('show', AttributeType.BOOL, nullable=False).expected == 'bool'


def test_spec_as_dict():
    spec = AttributeSpec('label', AttributeType.STR, nullable=False, known=True, required=True, choices=('a',))
    data = spec.as_dict()
    assert data == {'name': 'label', 'type': 'str', 'nullable': False, 'known': True, 'required': True,
                    'choices': ['a'], 'strict': False, 'deprecated': [], 'title': '', 'hint': '', 'hidden': False}


def test_strict_accepts_only_choices():
    spec = AttributeSpec('position', AttributeType.STR, nullable=False, choices=('', 'left'), strict=True)
    assert spec.accepts('left') and spec.accepts('') and not spec.accepts('up')
    assert spec.expected == "'' | 'left'"
    assert AttributeSpec('kind', AttributeType.STR, nullable=False, choices=('a',)).accepts('b')


def test_report_ok_depends_on_problems_only():
    report = NormalizationReport(conversions=[ValueConversion(0, 'a', 'wz', '1', 1)])
    assert report.ok
    report.problems.append(ValueProblem(0, 'a', 'wz', 'x', 'int | null'))
    assert not report.ok
    assert report.as_dict()['problems'][0]['expected'] == 'int | null'
