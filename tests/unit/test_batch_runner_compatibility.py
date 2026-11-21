"""Batch execution must preserve scientific arguments and historical artifacts."""
import json
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

import numpy as np
import pytest

from tsp_pso.application import runner
from tsp_pso.experiments.batch_executor import execute_one
from tsp_pso.experiments.experiment_batch import (
    DatasetDescriptor,
    compile_plan,
    iterate_runs,
)
from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)
from tsp_pso.infrastructure import experiment_options, run_storage


@pytest.mark.parametrize('mode', ['tsp', 'tspwr'])
@pytest.mark.parametrize('style', ['standard', 'berlin_grid', 'bays', 'fuel'])
@pytest.mark.parametrize('verbose,excel', [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize('operator,reset,ring', [(3, False, False), (15, True, True)])
def test_batch_matches_historical_solver_and_artifacts(tmp_path, monkeypatch, mode, style,
                                                     verbose, excel, operator, reset, ring):
    class Clock:
        @staticmethod
        def now(tz):
            return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(run_storage, 'datetime', Clock)
    descriptor = DatasetDescriptor('sample', 'saved.json', 'json', 'saved', ('tsp', 'tspwr'))
    config = ExperimentConfiguration(
        datasets=('sample',), problem_modes=(mode,), particles=(4,), c1=(7,),
        operators=(operator,), ring=(ring,), permutation_reset=(reset,),
        k=(9,), primary_operator_share=(.37,), minimum_reset_probability=(.13,),
        maximum_reset_probability=(.71,), reset_threshold_divisor=(321,),
        fuel_capacity=(123.5,), consumption=(4.25,), full_initial_tank=(True,),
        progress_warmup_multiplier=(2.5,), repetitions=RepetitionSpec(1, 17),
        verbose=verbose, excel=excel, legacy_style=style, legacy_label='saved:label',
        analysis_output='historic.xlsx')
    run = next(iterate_runs(compile_plan(config, (descriptor,))))
    # Persisted evidence wins even for inactive axes; do not recalculate defaults.
    values = dict(run.legacy_values)
    values['reset_threshold_divisor'] = 654
    run = replace(run, legacy_values=tuple(values.items()))
    matrix = np.array([[0., 2.], [2., 0.]])
    prices = np.array([3., 5.])
    reader = Mock(return_value=(matrix, prices))
    monkeypatch.setattr(runner, '_load_dataset', reader)
    monkeypatch.setattr(experiment_options, 'load_catalog_options', Mock(side_effect=AssertionError('live catalog')))
    selected, other = Mock(), Mock()
    for key, factory in ((mode, selected), ('tspwr' if mode == 'tsp' else 'tsp', other)):
        monkeypatch.setitem(runner.SOLVER_REGISTRY, key, (factory, runner.SOLVER_REGISTRY[key][1]))
    from tsp_pso.algorithms.core.pso_config import PSOConfig
    from tsp_pso.algorithms.tspwr.refuel_config import RefuelConfig
    expected_init = dict(config=PSOConfig(N=4, c1=7, ring_mode=ring,
        reset_threshold_divisor=654, primary_operator_share=.37, progress_warmup_multiplier=2.5),
        refuel=RefuelConfig(max_capacity=123.5, consumption=4.25, full_init=True))
    suffix = {'standard': '9_0.13_0.71_17', 'berlin_grid': '9_17_0.13_0.71',
              'bays': '17', 'fuel': f'{ring}_True_17'}[style]
    filename = f'sample_True_4_7_{operator}_{suffix}.xlsx'
    expected_run = dict(verbose=verbose, optType=operator, excel=excel,
                        permutReset=reset, minPermut=.13, maxPermut=.71, k=9)
    actual = execute_one(run, tmp_path / 'runs' / '1', descriptor)
    assert actual.parent == tmp_path / 'runs' / '1' / 'sample'
    assert actual.name == f'2026-01-02_03-04-05_N4_c17_opt{operator}_ring{ring}_fullTrue_k9_min0.13_max0.71'
    expected_snapshot = {
        'dataset': 'sample', 'label': 'saved-label', 'steps': [7], 'particles': [4],
        'opts': [operator], 'minimums': [.13], 'maximums': [.71], 'rings': [ring], 'full_tanks': [True],
        'repetitions': {'start': 17, 'stop': 18, 'step': 1}, 'excel': excel, 'refuel': mode == 'tspwr',
        'style': style, 'max_capacity': 123.5, 'consumption': 4.25, 'permut_reset': reset, 'k': 9,
        'analysis_output': 'historic.xlsx', 'reset_threshold_divisor': 654,
        'primary_operator_share': .37, 'progress_warmup_multiplier': 2.5, 'verbose': verbose,
        'created_at': '2026-01-02T03:04:05+00:00'}
    assert (actual / 'run_config.json').read_bytes() == (
        json.dumps(expected_snapshot, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    saved = json.loads((actual / 'run_config.json').read_text())
    assert saved['repetitions'] == {'start': 17, 'stop': 18, 'step': 1}
    assert saved['reset_threshold_divisor'] == 654
    assert saved['label'] == 'saved-label'
    assert selected.call_count == 1
    actual_init = selected.call_args.kwargs
    assert actual_init['matrix'] is matrix
    assert actual_init['config'] == expected_init['config']
    assert actual_init['config'].reset_threshold_divisor == 654
    if mode == 'tspwr':
        assert actual_init['prices'] is prices
        assert actual_init['refuel'] == expected_init['refuel']
    else:
        assert set(actual_init) == {'matrix', 'config'}
    expected_run['file_path'] = actual / filename
    selected.return_value.run.assert_called_once_with(**expected_run)
    assert expected_run['verbose'] is verbose and expected_run['excel'] is excel
    assert expected_run['permutReset'] is reset and expected_run['k'] == 9
    other.assert_not_called()
    assert reader.call_args.args[0] == dict(filename='saved.json', format='json',
                                          source='saved', problem_types=('tsp', 'tspwr'))


def test_repeated_concrete_execution_preserves_previous_artifacts(tmp_path, monkeypatch):
    from pathlib import Path

    from conftest import concrete_run
    run = concrete_run(ExperimentConfiguration(
        datasets=('sample',), legacy_label='repeat', c1=(2,), excel=True, verbose=True,
    ))
    descriptor = DatasetDescriptor('sample', 'unused', 'json', 'test', ('tsp',))
    monkeypatch.setattr(runner, '_load_dataset', Mock(return_value=(None, None)))
    clock = Mock()
    clock.now.return_value = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(run_storage, 'datetime', clock)
    solver = Mock()
    solver.return_value.run.side_effect = lambda **kw: Path(kw['file_path']).write_bytes(b'raw history')
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (solver, runner.SOLVER_REGISTRY['tsp'][1]))
    first = execute_one(run, tmp_path, descriptor)
    before = {p.name: p.read_bytes() for p in first.iterdir()}
    second = execute_one(run, tmp_path, descriptor)
    assert second.name == first.name + '__2'
    assert first.parent == second.parent == tmp_path / 'sample'
    assert {p.name: p.read_bytes() for p in first.iterdir()} == before
    assert {p.name: p.read_bytes() for p in second.iterdir()} == before
    assert solver.call_count == 2
