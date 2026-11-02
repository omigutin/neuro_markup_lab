""" Модель документа: поля LabelMe, фигуры, неизвестные поля документа. """

from neuro_markup_lab.markup import MarkupDocument, MarkupShape

from ..conftest import make_document


def test_reads_document_with_shapes(sample_shapes):
    document = MarkupDocument.model_validate(make_document(sample_shapes))
    assert len(document.shapes) == 2 and isinstance(document.shapes[0], MarkupShape)
    assert document.shapes[1].attribute('zone_kind') == 'a'
    assert document.lineColor == (0, 255, 0, 128)


def test_unknown_document_fields_kept():
    data = MarkupDocument.model_validate({'shapes': [], 'camera_note': 'x'}).model_dump(mode='json')
    assert data['camera_note'] == 'x' and data['imageWidth'] == 1920
