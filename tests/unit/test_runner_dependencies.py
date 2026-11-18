"""Explicit execution inputs and absence of import-time configuration state."""
from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys
from unittest.mock import Mock

import numpy as np
import pytest

from tsp_pso.application import runner
from tsp_pso.experiments.experiment import Experiment, build_experiments
from tsp_pso.experiments.experiment_batch import compile_plan, iterate_runs, load_presets
from tsp_pso.experiments import batch_executor
from tsp_pso.infrastructure.experiment_options import load_run_options

pytestmark = pytest.mark.unit


def test_runner_import_has_no_configuration_side_effects():
    code = '''
import json
from unittest.mock import patch
from tsp_pso.experiments import experiment
from tsp_pso.infrastructure import experiment_options
with patch.object(json, 'load', side_effect=AssertionError('JSON read')), \\
     patch.object(experiment_options, 'load_run_options', side_effect=AssertionError('options loaded')), \\
     patch.object(experiment, 'build_experiments', side_effect=AssertionError('experiments built')):
    from tsp_pso.application import runner
assert not {'RUN_OPTIONS', 'DATASETS', 'EXPERIMENTS'} & vars(runner).keys()
'''
    result = subprocess.run([sys.executable, '-B', '-c', code],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_datasets_are_independent(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'load_run_options', Mock(side_effect=AssertionError('implicit options')))
    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    experiment = Experiment(dataset='same-id', label='independent', steps=(2,), excel=False, refuel=True)
    descriptors = []
    for i in (1, 2):
        path = tmp_path / f'{i}.json'
        path.write_text(json.dumps({'nodes': [
            {'latitude': 0, 'longitude': 0, 'price': i},
            {'latitude': 0, 'longitude': i, 'price': i + 1}]}))
        descriptors.append({'filename': path.name, 'format': 'json'})
    original = deepcopy(descriptors)
    destinations = [runner.execute(experiment, tmp_path / 'output', dataset=d, datasets_root=tmp_path)
                    for d in descriptors]
    assert descriptors == original
    first, second = [call.kwargs for call in factory.call_args_list]
    np.testing.assert_array_equal(first['prices'], [1., 2.])
    np.testing.assert_array_equal(second['prices'], [2., 3.])
    assert first['matrix'][0, 1] < second['matrix'][0, 1]
    assert destinations[0] != destinations[1]
    assert all(json.loads((p / 'run_config.json').read_text())['dataset'] == 'same-id' for p in destinations)
    assert not {'RUN_OPTIONS', 'DATASETS', 'EXPERIMENTS'} & vars(runner).keys()


def test_execute_uses_supplied_options_and_default_output(tmp_path, monkeypatch):
    options = {'datasets': {'sample': {'filename': 'supplied', 'format': 'matrix'}}, 'output_dir': 'Results'}
    original = deepcopy(options)
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'load_run_options', Mock(side_effect=AssertionError('implicit options')))
    reader = Mock(return_value=(np.array([[0., 1.], [1., 0.]]), None))
    monkeypatch.setattr(runner, '_load_dataset', reader)
    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    experiment = Experiment(dataset='sample', label='options', steps=(2,), excel=False)
    destination = runner.execute(experiment, run_options=options)
    reader.assert_called_once_with(options['datasets']['sample'], tmp_path / 'datasets')
    assert destination.parent == tmp_path / 'Results' / 'sample'
    assert options == original


@pytest.mark.parametrize('fails', [False, True])
def test_batch_passes_snapshot_descriptor_without_catalog_mutation(tmp_path, monkeypatch, fails):
    from tsp_pso.experiments.experiment_batch import DatasetDescriptor

    run = next(iterate_runs(compile_plan(load_presets()[0])))
    descriptor = DatasetDescriptor(id=run.dataset, filename='saved/path.json', format='json',
                                   source='snapshot', problem_types=('tsp', 'tspwr'))
    execute = Mock(side_effect=RuntimeError('execution failed') if fails else None, return_value=tmp_path)
    monkeypatch.setattr(runner, 'execute', execute)
    monkeypatch.setattr(runner, 'load_run_options', Mock(side_effect=AssertionError('catalog access')))
    before = dict(vars(runner))
    if fails:
        with pytest.raises(RuntimeError, match='execution failed'):
            batch_executor.execute_one(run, tmp_path, descriptor)
    else:
        assert batch_executor.execute_one(run, tmp_path, descriptor) == tmp_path
    execute.assert_called_once_with(batch_executor.to_legacy_experiment(run), output_dir=tmp_path,
        dataset={'filename': descriptor.filename, 'format': descriptor.format,
                 'source': descriptor.source, 'problem_types': descriptor.problem_types})
    assert vars(runner) == before


def test_traditional_presets_and_configuration_order():
    options = load_run_options()
    experiments = build_experiments(options)
    assert len(experiments) == 22
    assert sum(e.count for e in experiments) == 1209
    assert experiments == runner.build_experiments()
    for experiment, preset in zip(experiments, load_presets()):
        old = list(experiment.configurations())
        new = [next(batch_executor.to_legacy_experiment(run).configurations())
               for run in iterate_runs(compile_plan(preset))]
        assert new == old
