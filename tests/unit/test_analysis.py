"""Numerical and file contracts for result analysis."""
import pandas as pd
import pytest

from tsp_pso.analysis import analysis

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('history, expected', [
    ([[9, 20], [7, 10], [3, 10]], (10, 7)),
    ([[3, 10], [9, 20], [7, 10]], (10, 3)),
    ([[None, None], [5, 14], [None, 20]], (14, 5)),
])
def test_history_minimum_preserves_row_order_and_missing_values(history, expected):
    frame = pd.DataFrame(history, columns=['Step', 'Result'])
    original = frame.copy(deep=True)
    assert analysis._history_minimum(frame) == expected
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('frame, message', [
    (pd.DataFrame(columns=['Step', 'Result']), 'does not contain valid results'),
    (pd.DataFrame({'Step': [1, 2], 'Result': [None, None]}), 'does not contain valid results'),
    (pd.DataFrame({'Step': [None, 2], 'Result': [1, 1]}), 'minimum result has no Step'),
    (pd.DataFrame({'Result': [1]}), 'missing Result or Step'),
    (pd.DataFrame({'Step': [1]}), 'missing Result or Step'),
])
def test_unusable_history(frame, message):
    with pytest.raises(ValueError, match=message):
        analysis._history_minimum(frame)


def test_all_metrics_and_summary_excel_contract(tmp_path):
    definition = {
        'parameters': {'operator': [3, 1]}, 'columns': ['operator'],
        'repetitions': {'start': 1, 'stop': 3},
        'input_template': '{operator}_{number}.xlsx', 'output': 'summary/Analysis.xlsx',
    }
    for operator in (3, 1):
        for number, history in enumerate(([[9, 20], [7, 10], [3, 10]],
                                          [[5, 14], [1, 18]]), 1):
            pd.DataFrame(history, columns=['Step', 'Result']).to_excel(
                tmp_path / f'{operator}_{number}.xlsx', index=False)
    actual = analysis.analyze(definition, root=tmp_path)
    expected = pd.DataFrame({
        'operator': [3, 1], 'mean_minimum_result': [12., 12.],
        'mean_step_of_minimum': [6., 6.], 'best_result': [10, 10],
    })
    pd.testing.assert_frame_equal(actual, expected)
    pd.testing.assert_frame_equal(pd.read_excel(tmp_path / 'summary/Analysis.xlsx'),
                                  expected, check_dtype=False)


def test_catalog_definitions_preserve_names_columns_and_order(monkeypatch):
    from pathlib import Path
    from tsp_pso.experiments.experiment import build_experiments
    from tsp_pso.experiments.result_naming import result_filename

    options = analysis.load_run_options()
    experiments = build_experiments(options)
    calls = []

    def build_once(options):
        calls.append(options)
        return experiments

    monkeypatch.setattr(analysis, 'build_experiments', build_once)
    definitions = analysis.load_analysis_options()
    assert len(calls) == 1
    assert definitions[:2] == options['historical_analyses']
    assert len(definitions[2:]) == len(experiments) == 22
    for definition, experiment in zip(definitions[2:], experiments):
        assert definition['experiment'] == {'dataset': experiment.dataset, 'label': experiment.label}
        columns = ['random', 'N', 'c1', 'optType']
        if experiment.style == 'fuel':
            columns += ['ring', 'full']
        elif experiment.style != 'bays':
            columns += ['kv', 'minR', 'maxR']
        assert definition['columns'] == columns
        assert definition['output'] == str(Path(options['output_dir']) / experiment.dataset /
            (experiment.analysis_output or f'Analysis_{experiment.dataset}_{experiment.label}.xlsx'))
        for configuration in experiment.configurations():
            n, c1, opt, minimum, maximum, ring, full, number = configuration
            actual = Path(definition['input_template'].format(
                N=n, c1=c1, optType=opt, minR=minimum, maxR=maximum,
                ring=ring, full=full, number=number))
            assert actual.name == result_filename(experiment, configuration)


@pytest.mark.parametrize('matches', [0, 2])
def test_public_analysis_reference_requires_exactly_one_match(matches):
    options = analysis.load_run_options()
    options['experiments'] = options['experiments'][:1] * matches
    reference = {'id': 'selection', 'experiment': {'dataset': 'berlin52', 'label': 'individual'},
                 'output': None}
    with pytest.raises(ValueError, match='must match exactly one run'):
        analysis.analysis_for_experiment(reference, options)
