"""Contracts for pure preset conversion and its compatible JSON loader."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from tsp_pso.experiments import experiment_batch
from tsp_pso.experiments.batch_executor import to_legacy_experiment
from tsp_pso.experiments.experiment import build_experiments
from tsp_pso.experiments.experiment_config import RepetitionSpec
from tsp_pso.infrastructure.experiment_options import load_run_options

pytestmark = pytest.mark.unit


@pytest.fixture
def options():
    return {
        'output_dir': 'relative/results',
        'defaults': dict(
            particles=[8], opts=[10], minimums=[.2], maximums=[.8],
            rings=[True], full_tanks=[False], repetitions=dict(start=1, stop=2),
            excel=False, verbose=False, refuel=False, style='standard',
            max_capacity=150.0, consumption=7.0, permut_reset=False,
            reset_threshold_divisor=1000, primary_operator_share=.2,
            progress_warmup_multiplier=5, k=10),
        'experiments': [dict(dataset='unregistered', label='first', steps=[3])],
    }


def test_catalog_presets_match_loader_and_ordered_traditional_configurations():
    options = load_run_options()
    presets = experiment_batch.build_presets(options)
    assert type(presets) is tuple
    assert presets == experiment_batch.load_presets()
    traditional = build_experiments(options)
    assert len(presets) == len(traditional) == 22
    assert [p.name for p in presets] == [f'{e.dataset}: {e.label}' for e in traditional]
    total = 0
    for preset, old in zip(presets, traditional):
        actual = [to_legacy_experiment(run)
                  for run in experiment_batch.iterate_runs(experiment_batch.compile_plan(preset))]
        expected = [replace(old, particles=(n,), steps=(c1,), opts=(operator,),
                            minimums=(minimum,), maximums=(maximum,), rings=(ring,),
                            full_tanks=(full,), repetitions=range(number, number + 1))
                    for n, c1, operator, minimum, maximum, ring, full, number
                    in old.configurations()]
        assert actual == expected
        total += len(actual)
    assert total == 1209


def test_overrides_replace_defaults_and_preserve_order(options):
    options['defaults']['analysis_output'] = 'inherited.xlsx'
    options['experiments'][0].update(particles=[16, 4], repetitions=dict(start=17, stop=20))
    options['experiments'].append(dict(dataset='other', label='second', steps=[9, 2]))
    first, second = experiment_batch.build_presets(options)
    assert first.particles == (16, 4)
    assert first.repetitions == RepetitionSpec(3, 17)
    assert first.analysis_output == second.analysis_output == 'inherited.xlsx'
    assert second.particles == (8,) and second.c1 == (9, 2)
    assert second.repetitions == RepetitionSpec(1, 1)
    assert [first.legacy_label, second.legacy_label] == ['first', 'second']


def test_nested_override_is_not_deeply_merged(options):
    options['experiments'][0]['repetitions'] = {'stop': 20}
    with pytest.raises(KeyError) as raised:
        experiment_batch.build_presets(options)
    assert raised.value.args == ('start',)


def test_inactive_values_are_preserved(options):
    options['experiments'][0].update(
        k=123456, minimums=[.9, .7], maximums=[.1, .3],
        max_capacity=234.5, consumption=8.125, full_tanks=[True, False],
        reset_threshold_divisor=234, primary_operator_share=.7,
        progress_warmup_multiplier=13)
    preset, = experiment_batch.build_presets(options)
    assert preset.k == (123456,)
    assert preset.minimum_reset_probability == (.9, .7)
    assert preset.maximum_reset_probability == (.1, .3)
    assert preset.fuel_capacity == (234.5,) and preset.consumption == (8.125,)
    assert preset.full_initial_tank == (True, False)
    assert preset.reset_threshold_divisor == (234,)
    assert preset.primary_operator_share == (.7,)
    assert preset.progress_warmup_multiplier == (13,)


@pytest.mark.parametrize('field,value,message', [
    ('particles', [], 'particles'),
    ('opts', [99], 'Unsupported operator'),
    ('k', 0, 'k'),
    ('style', 'unknown', 'legacy_style'),
    ('analysis_output', 'nested/result.xlsx', 'analysis_output'),
    ('repetitions', {'start': 1, 'stop': 1}, 'repetitions.count'),
])
def test_model_validation_propagates(options, field, value, message):
    options['experiments'][0][field] = value
    original = deepcopy(options)
    with pytest.raises(ValueError, match=message):
        experiment_batch.build_presets(options)
    assert options == original


@pytest.mark.parametrize('missing', ['output_dir', 'defaults', 'experiments'])
def test_missing_options_raise_key_error(options, missing):
    del options[missing]
    with pytest.raises(KeyError) as raised:
        experiment_batch.build_presets(options)
    assert raised.value.args == (missing,)


def test_build_is_independent_of_files_paths_and_global_configuration(options, tmp_path, monkeypatch):
    expected = experiment_batch.build_presets(options)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(experiment_batch, 'ROOT', None)
    forbidden = Mock(side_effect=AssertionError('File access during conversion'))
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(json, 'load', forbidden)
    assert experiment_batch.build_presets(options) == expected
    assert expected[0].output_dir == Path('relative/results')
    forbidden.assert_not_called()


def test_inputs_are_not_mutated_or_aliased(options):
    original = deepcopy(options)
    preset, = experiment_batch.build_presets(options)
    assert options == original
    options['defaults']['particles'].append(16)
    options['experiments'][0]['steps'].append(9)
    options['defaults']['repetitions']['stop'] = 99
    assert preset.particles == (8,) and preset.c1 == (3,)
    assert preset.repetitions == RepetitionSpec(1, 1)
    payload = preset.to_dict()
    payload['particles'].append(32)
    assert options['defaults']['particles'] == [8, 16]


def test_load_presets_reads_original_path_and_delegates(options, tmp_path, monkeypatch):
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'experiments.json').write_text(json.dumps(options), encoding='utf-8')
    monkeypatch.setattr(experiment_batch, 'ROOT', tmp_path)
    expected = experiment_batch.build_presets(options)
    build = Mock(return_value=expected)
    monkeypatch.setattr(experiment_batch, 'build_presets', build)
    assert experiment_batch.load_presets() is expected
    build.assert_called_once_with(options)
