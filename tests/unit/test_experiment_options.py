"""Path resolution and import independence of experiment option loading."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tsp_pso.infrastructure.experiment_options import load_run_options

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('combined', [False, True])
@pytest.mark.parametrize('relative', [False, True])
def test_explicit_configuration_paths(tmp_path, monkeypatch, combined, relative):
    directory = tmp_path / 'configuration'
    directory.mkdir()
    expected = {'defaults': {}, 'experiments': [], 'output_dir': 'unchanged-relative',
                'datasets': {'sample': {'filename': 'unchanged-dataset'}},
                'historical_analyses': []}
    if combined:
        (directory / 'custom.json').write_text(json.dumps(expected))
    else:
        (directory / 'custom.json').write_text(json.dumps({
            key: value for key, value in expected.items()
            if key not in ('datasets', 'historical_analyses')}))
        for section in ('datasets', 'historical_analyses'):
            (directory / f'{section}.json').write_text(json.dumps({section: expected[section]}))
    monkeypatch.chdir(tmp_path)
    path = Path('configuration/custom.json') if relative else directory / 'custom.json'
    assert load_run_options(path) == expected
    assert load_run_options(str(path)) == expected


def test_default_path_and_runner_reexport(tmp_path, monkeypatch):
    from tsp_pso.application import runner

    expected = load_run_options()
    monkeypatch.chdir(tmp_path)
    assert runner.load_run_options is load_run_options
    assert load_run_options() == load_run_options(None) == load_run_options('') == expected
    assert runner.load_run_options() == expected
    assert not {'RUN_OPTIONS', 'DATASETS', 'EXPERIMENTS'} & vars(runner).keys()


def test_analysis_loading_does_not_import_runner():
    result = subprocess.run([
        sys.executable, '-B', '-c',
        'import sys; '
        'from tsp_pso.analysis.analysis import load_run_options, load_analysis_options; '
        'from tsp_pso.infrastructure.experiment_options import load_run_options as reader; '
        'assert load_run_options is reader; '
        'assert len(load_analysis_options()) == 24; '
        'assert "tsp_pso.application.runner" not in sys.modules',
    ], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
