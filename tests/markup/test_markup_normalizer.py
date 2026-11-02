""" Приведение типов во всём документе. """

from neuro_markup_lab.markup import MarkupAttributeSchema, MarkupNormalizer


def normalize(document: dict):
    schema = MarkupAttributeSchema.for_shapes(document['shapes'])
    return MarkupNormalizer(schema).normalize(document)


def test_converts_known_and_reports():
    document = {'shapes': [{'label': 'crop', 'points': [[1, 2]], 'wz': '1', 'group_id': '', 'show': 'false'}]}
    report = normalize(document)
    shape = document['shapes'][0]
    assert shape['wz'] == 1 and shape['group_id'] is None and shape['show'] is False
    assert report.ok
    assert {c.field for c in report.conversions} == {'wz', 'group_id', 'show'}
    assert report.conversions[0].label == 'crop'


def test_problem_keeps_value_and_blocks():
    document = {'shapes': [{'label': 'crop', 'wz': 'abc'}]}
    report = normalize(document)
    assert not report.ok
    assert document['shapes'][0]['wz'] == 'abc'
    problem = report.problems[0]
    assert (problem.shape_index, problem.field, problem.expected) == (0, 'wz', 'int | null')


def test_points_and_shape_type_untouched():
    document = {'shapes': [{'label': 'crop', 'points': [[1, 2]], 'shape_type': 'point'}]}
    assert normalize(document).conversions == []
    assert document['shapes'][0]['points'] == [[1, 2]]


def test_document_field_unified_across_shapes():
    document = {'shapes': [{'label': 'crop', 'count': 1}, {'label': 'input', 'count': '2'}]}
    report = normalize(document)
    assert [s['count'] for s in document['shapes']] == [1, 2]
    assert len(report.conversions) == 1


def test_document_without_shapes():
    assert normalize({'shapes': []}).ok
    report = MarkupNormalizer(MarkupAttributeSchema()).normalize({'version': '1'})
    assert report.ok and not report.conversions


def test_report_as_dict():
    document = {'shapes': [{'label': 'crop', 'wz': '1'}, {'label': 'input', 'wz': 'x'}]}
    data = normalize(document).as_dict()
    assert data['conversions'][0]['after'] == 1
    assert data['problems'][0]['value'] == 'x'


def test_values_outside_enum_block_save():
    document = {'shapes': [{'label': 'crop2', 'position': 'up'}, {'label': 'promt', 'position': ''}]}
    report = normalize(document)
    assert [(p.shape_index, p.field) for p in report.problems] == [(0, 'label'), (0, 'position')]
    assert "'crop'" in report.problems[0].expected
