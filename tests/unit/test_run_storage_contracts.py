"""Path, reservation and failure contracts of execution storage."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from tsp_pso.experiments.experiment import Experiment
from tsp_pso.infrastructure import run_storage

pytestmark = pytest.mark.unit


@pytest.fixture
def experiment():
    return Experiment(dataset='sample', label='configuración', particles=(2, 4),
                      steps=(100, 200, 300), repetitions=range(2, 8, 2), excel=False)


@pytest.fixture
def clock(monkeypatch):
    clock = Mock()
    clock.now.return_value = datetime(2026, 10, 3, 21, 45, 32, 123456, tzinfo=timezone.utc)
    monkeypatch.setattr(run_storage, 'datetime', clock)
    return clock


def test_reservation_collisions_and_exact_snapshot(tmp_path, experiment, clock):
    directories = [run_storage.create_run_directory(experiment, tmp_path) for _ in range(3)]
    assert [p.name for p in directories] == [directories[0].name,
                                           directories[0].name + '__2',
                                           directories[0].name + '__3']
    assert directories[0].name.startswith('2026-10-03_21-45-32_N2-4_c1100-300x3_')
    assert all(call.args == (timezone.utc,) for call in clock.now.call_args_list)
    expected = asdict(experiment)
    expected['repetitions'] = {'start': 2, 'stop': 8, 'step': 2}
    expected['created_at'] = '2026-10-03T21:45:32+00:00'
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
    monkeypatch.setattr(runner, 'RUN_OPTIONS', {'output_dir': configured})
    output = {'default': None, 'default_absolute': None, 'relative': 'relative',
              'absolute': tmp_path / 'absolute', 'empty': ''}[mode]
    expected = project / configured if output is None else Path(output)
    directory = runner.create_run_directory(experiment, output)
    assert directory.parent == expected / experiment.dataset
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
        run_storage.create_run_directory(experiment, tmp_path)
    assert raised.value is error
    if stage == 'snapshot':
        assert len(list((tmp_path / 'sample').iterdir())) == 1


def test_import_does_not_load_runner():
    result = subprocess.run([sys.executable, '-B', '-c',
        'import sys; from tsp_pso.infrastructure.run_storage import create_run_directory; '
        'assert "tsp_pso.application.runner" not in sys.modules'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
