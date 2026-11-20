"""Execution storage and analysis integration with real JSON and Excel files."""

from dataclasses import asdict, replace
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from tsp_pso.infrastructure.experiment_options import load_run_options
from tsp_pso.experiments.experiment import Experiment, build_experiments
from tsp_pso.analysis import analysis
from tsp_pso.application import runner

from tsp_pso.analysis.analysis import extra_filename_fields, historical_result_filename as result_filename

pytestmark = pytest.mark.functional


@pytest.fixture
def historical_run():
    """Write historical reader inputs, without any execution or production storage API."""
    count = 0
    def write(experiment, *, output_dir):
        nonlocal count
        parent = Path(output_dir) / experiment.dataset
        parent.mkdir(parents=True, exist_ok=True)
        directory = parent / f'2026-10-03_21-45-32_fixture_{len(list(parent.iterdir()))}'
        directory.mkdir()
        saved = asdict(experiment)
        saved['repetitions'] = dict(start=experiment.repetitions.start,
                                   stop=experiment.repetitions.stop, step=experiment.repetitions.step)
        saved['created_at'] = '2026-10-03T21:45:32+00:00'
        (directory / 'run_config.json').write_text(json.dumps(saved), encoding='utf-8')
        if experiment.excel:
            for configuration in experiment.configurations():
                count += 1
                pd.DataFrame({'Step': [5, 13], 'Result': [100 + count, 10 + count]}).to_excel(
                    directory / result_filename(experiment, configuration), index=False)
        return directory
    return write


@pytest.fixture
def experiment():
    return Experiment(dataset='Minas24D', label='storage test', steps=(2,),
                             particles=(2,), opts=(3,), repetitions=range(1, 3),
                             excel=True, analysis_output='Analysis_Minas24D.xlsx')


def test_analysis_discovers_all_runs_and_keeps_results_separate(historical_run, experiment, tmp_path, monkeypatch):
    first = historical_run(experiment, output_dir=tmp_path)
    second = historical_run(replace(experiment, label='different label'), output_dir=tmp_path)
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
    monkeypatch.setattr(analysis, 'load_run_options', lambda: {})
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


def test_catalog_analysis_entry_scans_dataset_runs(historical_run, experiment, tmp_path):
    selected = next(a for a in analysis.load_analysis_options()
                    if a.get('experiment') == {'dataset': 'Minas24D', 'label': 'individual'})
    assert analysis.analyze(selected, root=tmp_path) == {}
    first = historical_run(experiment, output_dir=tmp_path / 'Results')
    second = historical_run(replace(experiment, label='arbitrary UI label'), output_dir=tmp_path / 'Results')
    assert set(analysis.analyze(selected, root=tmp_path)) == {str(first), str(second)}


@pytest.mark.parametrize('damage', ['missing', 'empty', 'invalid_columns', 'corrupt'])
def test_incomplete_run_does_not_block_valid_run(historical_run, experiment, tmp_path, damage):
    broken = historical_run(experiment, output_dir=tmp_path)
    good = historical_run(experiment, output_dir=tmp_path)
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


def test_all_catalog_paths_are_unique_and_names_preserved(historical_run, tmp_path):
    paths = []
    for experiment in build_experiments(load_run_options()):
        directory = historical_run(replace(experiment, excel=False), output_dir=tmp_path)
        assert extra_filename_fields(experiment) == []
        paths.extend(directory / result_filename(experiment, c)
                     for c in experiment.configurations())
    assert len(paths) == 1209
    assert len(set(paths)) == len(paths)
    assert len(list(tmp_path.glob('*/*/run_config.json'))) == 22


@pytest.mark.parametrize('style', ['standard', 'berlin_grid', 'fuel', 'bays'])
def test_omitted_sweep_axes_get_unique_filenames_and_analysis(historical_run, experiment, tmp_path, style):
    experiment = replace(experiment, style=style, rings=(False, True),
                         full_tanks=(False, True), minimums=(0.2, 0.4),
                         maximums=(0.6, 0.8), repetitions=range(1, 2))
    directory = historical_run(experiment, output_dir=tmp_path)
    assert len(list(directory.glob('*.xlsx'))) == 16
    result = analysis.analyze_runs(directory.parent)[str(directory)]
    assert len(result) == 16
    assert set(result['mean_minimum_result']) == set(range(11, 27))


def test_excel_disabled_still_saves_configuration(historical_run, experiment, tmp_path):
    directory = historical_run(replace(experiment, excel=False), output_dir=tmp_path)
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
    result = analysis.analyze(historical, root=tmp_path)
    assert result['optType'].tolist() == [1, 2, 3, 4, 5]
    assert result['mean_minimum_result'].tolist() == [15.5, 25.5, 35.5, 45.5, 55.5]


def test_saved_repetition_step_is_preserved(historical_run, experiment, tmp_path):
    directory = historical_run(replace(experiment, repetitions=range(1, 6, 2)), output_dir=tmp_path)
    assert len(list(directory.glob('*.xlsx'))) == 3
    result = analysis.analyze_runs(directory.parent)[str(directory)]
    assert result['mean_minimum_result'].tolist() == [12]


def test_discovered_relative_paths_survive_working_directory_change(historical_run,
        experiment, tmp_path, monkeypatch):
    directory = historical_run(experiment, output_dir=tmp_path / 'working' / 'Results')
    monkeypatch.chdir(tmp_path / 'working')
    selected, = analysis.discover_run_analyses(Path('Results/Minas24D'))
    assert Path(selected['run_directory']) == directory
    assert Path(selected['input_template']).is_absolute()
    assert Path(selected['output']) == directory / 'Analysis_Minas24D.xlsx'
    monkeypatch.chdir(tmp_path)
    result = analysis.analyze(selected)
    assert result['mean_minimum_result'].tolist() == [11.5]
    pd.testing.assert_frame_equal(pd.read_excel(directory / 'Analysis_Minas24D.xlsx'),
                                  result, check_dtype=False)
    assert not (tmp_path / 'Results').exists()
    assert set(analysis.analyze_runs(Path('working/Results/Minas24D'))) == {str(directory)}


def test_historical_explicit_absolute_paths_ignore_working_directory(tmp_path, monkeypatch):
    source = tmp_path / 'history.xlsx'
    destination = tmp_path / 'historical-summary.xlsx'
    pd.DataFrame({'Step': [7], 'Result': [12]}).to_excel(source, index=False)
    selected = {'parameters': {'optType': [1]}, 'columns': ['optType'],
                'repetitions': {'start': 1, 'stop': 2},
                'input_template': str(source), 'output': str(destination)}
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    result = analysis.analyze(selected, root=elsewhere)
    pd.testing.assert_frame_equal(pd.read_excel(destination), result, check_dtype=False)
    assert list(elsewhere.iterdir()) == []


@pytest.mark.parametrize('repetitions, omit_step', [
    (range(1, 6, 2), False), (range(5, 0, -2), False), (range(2, 5), True),
])
def test_snapshot_repetition_ranges(historical_run, experiment, tmp_path, repetitions, omit_step):
    directory = historical_run(replace(experiment, repetitions=repetitions), output_dir=tmp_path)
    snapshot = directory / 'run_config.json'
    if omit_step:
        saved = json.loads(snapshot.read_text())
        del saved['repetitions']['step']
        snapshot.write_text(json.dumps(saved))
    selected, = analysis.discover_run_analyses(directory.parent)
    assert list(analysis.repetition_numbers(selected)) == list(repetitions)
    result = analysis.analyze(selected)
    assert result['mean_minimum_result'].tolist() == [12.]
    assert result['mean_step_of_minimum'].tolist() == [13.]
    assert result['best_result'].tolist() == [11]


@pytest.mark.parametrize('repetitions', [
    {'start': 1, 'stop': 3, 'step': 0},
    {'start': 3, 'stop': 3},
    {'start': 3, 'stop': 1, 'step': 1},
    {'start': 1, 'stop': 3, 'step': -1},
])
def test_invalid_snapshot_repetitions_are_skipped(historical_run, experiment, tmp_path, repetitions, capsys):
    directory = historical_run(experiment, output_dir=tmp_path)
    snapshot = directory / 'run_config.json'
    saved = json.loads(snapshot.read_text())
    saved['repetitions'] = repetitions
    snapshot.write_text(json.dumps(saved))
    assert analysis.discover_run_analyses(directory.parent) == []
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('axis', ['steps', 'particles', 'opts', 'minimums', 'maximums',
                                  'rings', 'full_tanks'])
@pytest.mark.parametrize('value', [[], None, 'invalid'])
def test_snapshot_axes_remain_validated(historical_run, experiment, tmp_path, axis, value):
    directory = historical_run(experiment, output_dir=tmp_path)
    snapshot = directory / 'run_config.json'
    saved = json.loads(snapshot.read_text())
    saved[axis] = value
    snapshot.write_text(json.dumps(saved))
    assert analysis.discover_run_analyses(directory.parent) == []


def test_saved_excel_runs_remain_available_with_disabled_current_preset(historical_run,
        experiment, tmp_path, monkeypatch):
    directory = historical_run(experiment, output_dir=tmp_path)
    options = load_run_options()
    options['output_dir'] = str(tmp_path)
    for entry in options['experiments']:
        entry['excel'] = False
    monkeypatch.setattr(analysis, 'load_run_options', lambda path=None: options)
    selected = next(item for item in analysis.load_analysis_options()
                    if item.get('experiment') == {'dataset': 'Minas24D', 'label': 'individual'})
    execute = Mock()
    monkeypatch.setattr(runner, 'execute', execute)
    assert set(analysis.analyze(selected)) == {str(directory)}
    execute.assert_not_called()
    assert pd.read_excel(directory / 'Analysis_Minas24D.xlsx')['mean_minimum_result'].tolist() == [11.5]


def test_bad_history_diagnostic_does_not_block_other_runs(historical_run,
        experiment, tmp_path, capsys):
    broken = historical_run(experiment, output_dir=tmp_path)
    good = historical_run(experiment, output_dir=tmp_path)
    raw = next(broken.glob('*.xlsx'))
    pd.DataFrame({'Step': ['invalid'], 'Result': [1]}).to_excel(raw, index=False)
    selected = next(item for item in analysis.discover_run_analyses(broken.parent)
                    if item['run_directory'] == str(broken))
    with pytest.raises(ValueError) as caught:
        analysis.analyze(selected)
    assert str(raw) in str(caught.value)
    assert isinstance(caught.value.__cause__, TypeError)
    assert 'invalid' in str(caught.value)
    assert set(analysis.analyze_runs(tmp_path / 'Minas24D')) == {str(good)}
    output = capsys.readouterr().out
    assert f'Skipping run {broken}' in output
    assert str(raw) in output
    assert 'invalid' in output
