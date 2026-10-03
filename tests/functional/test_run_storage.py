"""Execution storage and analysis integration with real JSON and Excel files."""

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from tsp_pso import analysis, runner

pytestmark = pytest.mark.functional


@pytest.fixture
def frozen_clock(monkeypatch):
    clock = Mock()
    clock.now.return_value = datetime(2026, 10, 3, 21, 45, 32, tzinfo=timezone.utc)
    monkeypatch.setattr(runner, 'datetime', clock)


@pytest.fixture
def workbook_solver(monkeypatch):
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        if kwargs['excel']:
            pd.DataFrame({'Step': [5, 13], 'Result': [100 + len(calls), 10 + len(calls)]}).to_excel(
                kwargs['file_path'], index=False)

    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', lambda **kwargs: SimpleNamespace(run=run))
    return calls


@pytest.fixture
def experiment():
    return runner.Experiment(dataset='Minas24D', label='storage test', steps=(2,),
                             particles=(2,), opts=(3,), repetitions=range(1, 3),
                             excel=True, analysis_output='Analysis_Minas24D.xlsx')


def test_repeated_execution_in_same_second_never_overwrites(experiment, workbook_solver, frozen_clock, tmp_path):
    first = runner.execute(experiment, output_dir=tmp_path)
    original = {p.name: p.read_bytes() for p in first.iterdir()}
    second = runner.execute(experiment, output_dir=tmp_path)
    assert first != second
    assert first.parent == second.parent == tmp_path / 'Minas24D'
    assert first.name.startswith('2026-10-03_21-45-32_N2_c12_opt3_ringTrue_fullFalse_')
    assert second.name == first.name + '__2'
    assert {p.name: p.read_bytes() for p in first.iterdir()} == original
    assert len(list((tmp_path / 'Minas24D').iterdir())) == 2
    for directory in (first, second):
        assert {p.name for p in directory.glob('*.xlsx')} == {
            'Minas24D_True_2_2_3_10_0.2_0.8_1.xlsx',
            'Minas24D_True_2_2_3_10_0.2_0.8_2.xlsx',
        }
    assert [c['file_path'].parent for c in workbook_solver] == [first, first, second, second]


def test_snapshot_contains_complete_effective_configuration(workbook_solver, frozen_clock, tmp_path):
    options = runner.load_run_options()
    options['experiments'] = [{
        'dataset': 'Minas24D', 'label': 'snapshot', 'steps': [1000, 1200, 1400],
        'particles': [2, 4], 'rings': [True], 'full_tanks': [False],
        'repetitions': {'start': 3, 'stop': 5}, 'reset_threshold_divisor': 2000,
        'primary_operator_share': 0.4, 'progress_warmup_multiplier': 2,
    }]
    experiment, = runner.build_experiments(options)
    directory = runner.execute(experiment, output_dir=tmp_path)
    saved = json.loads((directory / 'run_config.json').read_text())
    expected = asdict(experiment)
    expected['repetitions'] = {'start': 3, 'stop': 5, 'step': 1}
    expected['created_at'] = '2026-10-03T21:45:32+00:00'
    assert saved == json.loads(json.dumps(expected))
    assert saved['particles'] == [2, 4]
    assert saved['steps'] == [1000, 1200, 1400]
    assert saved['reset_threshold_divisor'] == 2000
    assert saved['minimums'] == [0.2]
    assert 'c11000-1400x3' in directory.name
    assert len(workbook_solver) == 12
    assert all(c['file_path'].parent == directory for c in workbook_solver)


def test_analysis_discovers_all_runs_and_keeps_results_separate(experiment, workbook_solver, frozen_clock, tmp_path, monkeypatch):
    first = runner.execute(experiment, output_dir=tmp_path)
    second = runner.execute(replace(experiment, label='different label'), output_dir=tmp_path)
    root = tmp_path / 'Minas24D'
    invalid = root / '2026-10-03_21-45-32_invalid'
    invalid.mkdir()
    (invalid / 'run_config.json').write_text('{invalid json')
    missing = root / '2026-10-03_21-45-32_missing'
    missing.mkdir()
    incomplete_metadata = root / '2026-10-03_21-45-32_incomplete_metadata'
    incomplete_metadata.mkdir()
    (incomplete_metadata / 'run_config.json').write_text('{}')
    legacy = root / 'legacy'
    legacy.mkdir()
    (legacy / 'run_config.json').write_bytes((first / 'run_config.json').read_bytes())
    assert {a['run_directory'] for a in analysis.discover_run_analyses(root)} == {str(first), str(second)}

    # The saved configuration must suffice even if today's catalog changes.
    monkeypatch.setattr(runner, 'EXPERIMENTS', [])
    monkeypatch.setattr(runner, 'RUN_OPTIONS', {})
    monkeypatch.setattr(runner, 'DATASETS', {})
    results = analysis.analyze_runs(root)
    assert set(results) == {str(first), str(second)}
    assert results[str(first)]['mean_minimum_result'].tolist() == [11.5]
    assert results[str(second)]['mean_minimum_result'].tolist() == [13.5]
    for directory in (first, second):
        output = directory / 'Analysis_Minas24D.xlsx'
        pd.testing.assert_frame_equal(pd.read_excel(output), results[str(directory)], check_dtype=False)
        assert len(list(directory.glob('*.xlsx'))) == 3
    assert not (root / 'Analysis_Minas24D.xlsx').exists()
    assert len(analysis.analyze_runs(root)) == 2  # Existing summaries are not raw inputs.


def test_catalog_analysis_entry_scans_dataset_runs(experiment, workbook_solver, tmp_path):
    selected = next(a for a in analysis.load_analysis_options()
                    if a.get('experiment') == {'dataset': 'Minas24D', 'label': 'individual'})
    assert analysis.first_missing_result(selected, root=tmp_path) is not None
    first = runner.execute(experiment, output_dir=tmp_path / 'Results')
    second = runner.execute(replace(experiment, label='arbitrary UI label'), output_dir=tmp_path / 'Results')
    assert analysis.first_missing_result(selected, root=tmp_path) is None
    assert set(analysis.analyze(selected, root=tmp_path)) == {str(first), str(second)}


@pytest.mark.parametrize('damage', ['missing', 'empty', 'invalid_columns', 'corrupt'])
def test_incomplete_run_does_not_block_valid_run(experiment, workbook_solver, tmp_path, damage):
    broken = runner.execute(experiment, output_dir=tmp_path)
    good = runner.execute(experiment, output_dir=tmp_path)
    raw = next(broken.glob('*.xlsx'))
    if damage == 'missing':
        raw.unlink()
    elif damage == 'empty':
        pd.DataFrame(columns=['Step', 'Result']).to_excel(raw, index=False)
    elif damage == 'invalid_columns':
        pd.DataFrame({'Other': [1]}).to_excel(raw, index=False)
    else:
        raw.write_bytes(b'not an Excel file')
    assert set(analysis.analyze_runs(tmp_path / 'Minas24D')) == {str(good)}
    assert not (broken / 'Analysis_Minas24D.xlsx').exists()


def test_all_catalog_paths_are_unique_and_names_preserved(frozen_clock, tmp_path):
    paths = []
    for experiment in runner.EXPERIMENTS:
        directory = runner.create_run_directory(experiment, output_dir=tmp_path)
        assert runner.extra_filename_fields(experiment) == []
        paths.extend(directory / runner.result_filename(experiment, c)
                     for c in experiment.configurations())
    assert len(paths) == 1209
    assert len(set(paths)) == len(paths)
    assert len(list(tmp_path.glob('*/*/run_config.json'))) == 22


@pytest.mark.parametrize('style', ['standard', 'berlin_grid', 'fuel', 'bays'])
def test_omitted_sweep_axes_get_unique_filenames_and_analysis(experiment, workbook_solver, tmp_path, style):
    experiment = replace(experiment, style=style, rings=(False, True),
                         full_tanks=(False, True), minimums=(0.2, 0.4),
                         maximums=(0.6, 0.8), repetitions=range(1, 2))
    directory = runner.execute(experiment, output_dir=tmp_path)
    assert len(list(directory.glob('*.xlsx'))) == 16
    result = analysis.analyze_runs(directory.parent)[str(directory)]
    assert len(result) == 16
    assert set(result['mean_minimum_result']) == set(range(11, 27))


def test_excel_disabled_still_saves_configuration(experiment, workbook_solver, tmp_path):
    directory = runner.execute(replace(experiment, excel=False), output_dir=tmp_path)
    assert json.loads((directory / 'run_config.json').read_text())['excel'] is False
    assert not list(directory.glob('*.xlsx'))
    assert analysis.analyze_runs(directory.parent) == {}


def test_historical_analysis_keeps_legacy_paths(tmp_path):
    historical = analysis.load_analysis_options()[0]
    for operator in range(1, 6):
        for number in range(1, 11):
            path = tmp_path / historical['input_template'].format(optType=operator, number=number)
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({'Step': [1], 'Result': [operator * 10 + number]}).to_excel(path, index=False)
    assert analysis.first_missing_result(historical, root=tmp_path) is None
    result = analysis.analyze(historical, root=tmp_path)
    assert result['optType'].tolist() == [1, 2, 3, 4, 5]
    assert result['mean_minimum_result'].tolist() == [15.5, 25.5, 35.5, 45.5, 55.5]


def test_duplicate_configurations_are_rejected_before_writing(experiment, workbook_solver, tmp_path):
    experiment = replace(experiment, particles=(2, 2))
    with pytest.raises(ValueError, match='duplicate result filenames'):
        runner.execute(experiment, output_dir=tmp_path)
    assert workbook_solver == []
    assert not list(tmp_path.iterdir())


def test_saved_repetition_step_is_preserved(experiment, workbook_solver, tmp_path):
    directory = runner.execute(replace(experiment, repetitions=range(1, 6, 2)), output_dir=tmp_path)
    assert len(list(directory.glob('*.xlsx'))) == 3
    result = analysis.analyze_runs(directory.parent)[str(directory)]
    assert result['mean_minimum_result'].tolist() == [12]
