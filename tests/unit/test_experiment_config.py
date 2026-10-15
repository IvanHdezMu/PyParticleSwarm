"""Configuration-only checks: no datasets, network, runner, or solver calls."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from tsp_pso.experiment_config import (
    ExperimentConfiguration, RepetitionSpec, SUPPORTED_OPERATORS,
    is_parameter_active,
)

pytestmark = pytest.mark.unit

SWEEPS = {
    'datasets': ('unregistered',), 'problem_modes': ('tsp',),
    'particles': (4,), 'c1': (1200,), 'operators': (10,), 'k': (10,),
    'ring': (True,), 'permutation_reset': (True,),
    'minimum_reset_probability': (0.2,), 'maximum_reset_probability': (0.8,),
    'fuel_capacity': (150,), 'consumption': (7,), 'full_initial_tank': (False,),
    'reset_threshold_divisor': (1000,), 'primary_operator_share': (0.2,),
    'progress_warmup_multiplier': (5,),
}


def config(**kwargs):
    return ExperimentConfiguration(**{'datasets': ('unregistered',), **kwargs})


def test_minimal_tsp_and_tspwr():
    tsp = config()
    assert tsp.problem_modes == ('tsp',)
    assert tsp.output_dir == Path('Results')
    fuel = config(problem_modes=('tspwr',), fuel_capacity=(200.5,), consumption=(8,),
                  full_initial_tank=(False, True))
    assert fuel.fuel_capacity == (200.5,)
    assert fuel.consumption == (8,)
    assert not hasattr(fuel, 'refuel')


def test_order_and_requested_k_survive_json_round_trip():
    original = config(particles=(16, 4, 8), c1=(4800, 1200, 2400),
                      k=(10, 1000, 1000000), ring=(False, True),
                      operators=tuple(sorted(SUPPORTED_OPERATORS)),
                      repetitions=RepetitionSpec(4, 17), output_dir=Path('custom/results'))
    payload = json.loads(json.dumps(original.to_dict(), allow_nan=False))
    assert payload['k'] == [10, 1000, 1000000]
    assert payload['minimum_reset_probability'] == [0.2]
    assert type(payload['minimum_reset_probability'][0]) is float
    restored = ExperimentConfiguration.from_dict(payload)
    assert restored == original
    assert restored.particles == (16, 4, 8)
    assert restored.k == (10, 1000, 1000000)


@pytest.mark.parametrize('name', SWEEPS)
def test_all_required_collections_reject_empty_and_duplicates(name):
    with pytest.raises(ValueError, match=name):
        config(**{name: ()})
    with pytest.raises(ValueError, match='duplicate'):
        config(**{name: SWEEPS[name] * 2})


def test_normal_numeric_equality_rejects_duplicates():
    with pytest.raises(ValueError, match='duplicate'):
        config(consumption=(7, 7.0))


@pytest.mark.parametrize('name,values', [
    ('particles', (1,)), ('particles', (2.0,)), ('particles', (True,)),
    ('c1', (0,)), ('c1', (-1,)), ('c1', ('1200',)),
    ('k', (0,)), ('k', (-1,)), ('k', (1.5,)), ('k', (False,)),
    ('operators', (99,)), ('operators', (True,)), ('operators', (1.0,)),
    ('problem_modes', ('TSP',)), ('problem_modes', ('other',)),
    ('datasets', ('',)), ('datasets', (12,)),
    ('ring', (1,)), ('permutation_reset', ('false',)), ('full_initial_tank', (0,)),
    ('fuel_capacity', (0,)), ('fuel_capacity', (-10,)),
    ('consumption', (0,)), ('consumption', (-1,)),
    ('reset_threshold_divisor', (0,)), ('reset_threshold_divisor', (-1,)),
    ('progress_warmup_multiplier', (-1,)),
])
def test_invalid_values(name, values):
    with pytest.raises(ValueError):
        config(**{name: values})


@pytest.mark.parametrize('name', [
    'minimum_reset_probability', 'maximum_reset_probability', 'primary_operator_share',
])
@pytest.mark.parametrize('value', [-0.1, 1.1, True, '0.2', float('nan'), float('inf')])
def test_probability_and_share_validation(name, value):
    with pytest.raises(ValueError):
        config(**{name: (value,)})


@pytest.mark.parametrize('name', [
    'fuel_capacity', 'consumption', 'reset_threshold_divisor', 'progress_warmup_multiplier',
])
@pytest.mark.parametrize('value', [True, '7', float('nan'), float('inf'), -float('inf')])
def test_numeric_types_and_finiteness(name, value):
    with pytest.raises(ValueError):
        config(**{name: (value,)})


def test_no_artificial_integer_limits_or_probability_reordering():
    huge = 10**100
    value = config(particles=(huge,), c1=(huge,), k=(huge,),
                   repetitions=RepetitionSpec(huge, 17),
                   minimum_reset_probability=(1,), maximum_reset_probability=(0,))
    assert value.k == (huge,)
    assert ExperimentConfiguration.from_dict(json.loads(json.dumps(value.to_dict()))) == value


@pytest.mark.parametrize('first_id,count,last_id', [(17, 4, 20), (6, 5, 10)])
def test_legacy_repetition_labels(first_id, count, last_id):
    spec = RepetitionSpec(count=count, first_id=first_id)
    assert spec.first_id + spec.count - 1 == last_id


@pytest.mark.parametrize('kwargs', [
    {'count': 0}, {'count': -1}, {'count': True}, {'count': 1.5},
    {'first_id': 0}, {'first_id': False}, {'first_id': '17'},
])
def test_invalid_repetitions(kwargs):
    with pytest.raises(ValueError):
        RepetitionSpec(**kwargs)


def test_edit_safety_and_detached_serialization():
    values = [16, 8]
    original = config(particles=values)
    values.append(4)
    assert original.particles == (16, 8)
    with pytest.raises(FrozenInstanceError):
        original.name = 'changed'
    with pytest.raises(FrozenInstanceError):
        original.repetitions.count = 5
    updated = replace(original, k=(1000,))
    assert original.k == (10,) and updated.k == (1000,)
    payload = original.to_dict()
    payload['particles'].append(2)
    payload['repetitions']['count'] = 99
    assert original.particles == (16, 8) and original.repetitions.count == 1


@pytest.mark.parametrize('kwargs', [
    {'datasets': 'dataset'}, {'particles': {2, 4}}, {'name': ''},
    {'verbose': 1}, {'excel': 'true'}, {'output_dir': ''},
    {'output_dir': 5}, {'repetitions': 5},
])
def test_invalid_scalar_or_collection_shapes(kwargs):
    with pytest.raises(ValueError):
        config(**kwargs)


@pytest.mark.parametrize('payload', [None, {}, {'datasets': ['x'], 'typo': 1},
    {'datasets': ['x'], 'repetitions': 1},
    {'datasets': ['x'], 'repetitions': {'seed': 17}},
])
def test_invalid_serialized_payload(payload):
    with pytest.raises(ValueError):
        ExperimentConfiguration.from_dict(payload)


@pytest.mark.parametrize('operator', sorted(SUPPORTED_OPERATORS))
def test_operator_applicability(operator):
    context = dict(problem_mode='tsp', operator=operator, permutation_reset=True)
    assert is_parameter_active('k', **context) == (operator in {4, 5, 15})
    assert is_parameter_active('primary_operator_share', **context) == (operator in {12, 15, 21})


def test_conditional_rules_do_not_change_stored_values():
    context = dict(problem_mode='tsp', operator=10, permutation_reset=False)
    for name in ('fuel_capacity', 'consumption', 'full_initial_tank',
                 'minimum_reset_probability', 'maximum_reset_probability',
                 'reset_threshold_divisor'):
        assert not is_parameter_active(name, **context)
        assert is_parameter_active(name, problem_mode='tspwr', operator=15,
                                   permutation_reset=True)
    assert is_parameter_active('ring', **context)
    assert not is_parameter_active('progress_warmup_multiplier', **context, excel=False)
    assert is_parameter_active('progress_warmup_multiplier', **context, excel=False, verbose=True)
    value = config(k=(10, 1000), permutation_reset=(False,))
    assert value.k == (10, 1000)
    with pytest.raises(ValueError, match='Unknown'):
        is_parameter_active('typo', **context)
