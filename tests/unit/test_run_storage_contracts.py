"""Path, reservation and failure contracts of execution storage."""
import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from conftest import concrete_run

from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)
from tsp_pso.infrastructure import run_storage

pytestmark = pytest.mark.unit


@pytest.fixture
def experiment():
    return ExperimentConfiguration(
        datasets=('sample',), legacy_label='configuración', particles=(2,), c1=(100,),
        repetitions=RepetitionSpec(1, 2), excel=False, verbose=True,
    )

@pytest.fixture
def clock(monkeypatch):
    clock = Mock()
    clock.now.return_value = datetime(2026, 10, 3, 21, 45, 32, 123456, tzinfo=timezone.utc)
    monkeypatch.setattr(run_storage, 'datetime', clock)
    return clock


def test_reservation_collisions_and_exact_snapshot(tmp_path, experiment, clock):
    directories = [run_storage.create_run_directory(concrete_run(experiment), tmp_path, dict(concrete_run(experiment).legacy_values)) for _ in range(3)]
    assert [p.name for p in directories] == [directories[0].name,
                                           directories[0].name + '__2',
                                           directories[0].name + '__3']
    assert directories[0].name.startswith('2026-10-03_21-45-32_N2_c1100_')
    assert all(call.args == (timezone.utc,) for call in clock.now.call_args_list)
    expected = {
        'dataset': 'sample', 'label': 'configuración', 'steps': [100], 'particles': [2], 'opts': [10],
        'minimums': [.2], 'maximums': [.8], 'rings': [True], 'full_tanks': [False],
        'repetitions': {'start': 2, 'stop': 3, 'step': 1}, 'excel': False, 'refuel': False,
        'style': 'standard', 'max_capacity': 150.0, 'consumption': 7.0, 'permut_reset': True, 'k': 10,
        'analysis_output': None, 'reset_threshold_divisor': 1000, 'primary_operator_share': .2,
        'progress_warmup_multiplier': 5, 'verbose': True, 'created_at': '2026-10-03T21:45:32+00:00'}
    for directory in directories:
        assert (directory / 'run_config.json').read_bytes() == (
            json.dumps(expected, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        assert list(directory.iterdir()) == [directory / 'run_config.json']


@pytest.mark.parametrize('mode', ['default', 'default_absolute', 'relative', 'absolute', 'empty'])
def test_runner_path_contract(tmp_path, monkeypatch, experiment, mode):
    from tsp_pso.application import runner

    project = tmp_path / 'project'
    working = tmp_path / 'working'
    working.mkdir()
    monkeypatch.chdir(working)
    monkeypatch.setattr(runner, 'ROOT', project)
    configured = tmp_path / 'configured' if mode == 'default_absolute' else 'Results'
    output = {'default': None, 'default_absolute': None, 'relative': 'relative',
              'absolute': tmp_path / 'absolute', 'empty': ''}[mode]
    expected = project / configured if output is None else Path(output)
    monkeypatch.setattr(runner, '_load_dataset', Mock(return_value=(None, None)))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (Mock(), runner.SOLVER_REGISTRY['tsp'][1]))
    run = replace(concrete_run(experiment), output_dir=Path(configured))
    directory = runner.execute(run, output, dataset={})
    assert directory.parent == expected / experiment.datasets[0]
    assert (directory / 'run_config.json').is_file()


@pytest.mark.parametrize('stage', ['parent', 'reservation', 'snapshot'])
def test_storage_errors_propagate(tmp_path, monkeypatch, experiment, stage):
    original_mkdir = Path.mkdir
    original_open = Path.open
    error = PermissionError('storage denied')
    def mkdir(path, *args, **kwargs):
        if stage == 'parent' or (stage == 'reservation' and path.parent == tmp_path / 'sample'):
            raise error
        return original_mkdir(path, *args, **kwargs)
    def open_file(path, *args, **kwargs):
        if stage == 'snapshot' and path.name == 'run_config.json':
            assert args == ('x',)
            assert kwargs == {'encoding': 'utf-8'}
            raise error
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    monkeypatch.setattr(Path, 'open', open_file)
    with pytest.raises(PermissionError) as raised:
        run_storage.create_run_directory(concrete_run(experiment), tmp_path, dict(concrete_run(experiment).legacy_values))
    assert raised.value is error
    if stage == 'snapshot':
        assert len(list((tmp_path / 'sample').iterdir())) == 1


def test_import_does_not_load_runner():
    result = subprocess.run([sys.executable, '-B', '-c',
        'import sys; from tsp_pso.infrastructure.run_storage import create_run_directory; '
        'assert "tsp_pso.application.runner" not in sys.modules'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
