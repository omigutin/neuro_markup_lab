""" Разбор тела запроса сохранения. """

from pathlib import Path

import pytest

from neuro_markup_lab.lab import parse_save_request
from neuro_markup_lab.markup import AttributeType, MarkupError
from neuro_markup_lab.storage import MarkupVariant


def payload(**extra) -> dict:
    base = {'video': ' /v/plant_cam5_x.avi ', 'base_variant': 'production', 'target_variant': 'sidecar'}
    base.update(extra)
    return base


def test_minimal():
    req = parse_save_request(payload())
    assert req.video == Path('/v/plant_cam5_x.avi')
    assert req.base_variant == MarkupVariant.PRODUCTION and req.target_variant == MarkupVariant.SIDECAR
    assert req.changes == {} and req.fields == {} and not req.dry_run and not req.confirm_production


def test_changes_and_fields():
    req = parse_save_request(payload(
        changes={'1': {'points': [[1, 2], [3, 4]], 'shape_type': 'line', 'attributes': {'label': 'a'}}},
        fields={'zone_kind': {'type': 'int', 'nullable': True}}, dry_run=True, confirm_production=True))
    assert req.changes[1].shape_type == 'line' and req.changes[1].attributes == {'label': 'a'}
    assert req.fields['zone_kind'].type == AttributeType.INT and req.fields['zone_kind'].nullable
    assert req.dry_run and req.confirm_production


@pytest.mark.parametrize('extra', [
    {'video': ''},
    {'base_variant': 'corrected'},
    {'target_variant': None},
    {'changes': []},
    {'changes': {'x': {}}},
    {'changes': {'0': {'attributes': []}}},
    {'changes': {'0': {'points': 'abc'}}},
    {'changes': {'0': {'shape_type': 5}}},
    {'fields': {'Зона': {'type': 'int'}}},
    {'fields': {'zone': {'type': 'any'}}},
    {'fields': {'zone': {'type': 'list'}}},
    {'fields': {'zone': 'int'}},
    {'jsons_dir': 5},
])
def test_invalid(extra):
    with pytest.raises(MarkupError):
        parse_save_request(payload(**extra))


def test_flags_must_be_true_literally():
    req = parse_save_request(payload(dry_run='yes', confirm_production=1))
    assert not req.dry_run and not req.confirm_production
