"""Numerical and file contracts for result analysis."""
from zipfile import BadZipFile

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
    definition = {'columns': ['operator'], 'output': 'summary/Analysis.xlsx'}
    for operator in (3, 1):
        for number, history in enumerate(([[9, 20], [7, 10], [3, 10]],
                                          [[5, 14], [1, 18]]), 1):
            pd.DataFrame(history, columns=['Step', 'Result']).to_excel(
                tmp_path / f'{operator}_{number}.xlsx', index=False)
    actual = analysis.analyze(definition, root=tmp_path, groups=[
        ({'operator': op}, [f'{op}_{n}.xlsx' for n in (1, 2)]) for op in (3, 1)])
    expected = pd.DataFrame({
        'operator': [3, 1], 'mean_minimum_result': [12., 12.],
        'mean_step_of_minimum': [6., 6.], 'best_result': [10, 10],
    })
    pd.testing.assert_frame_equal(actual, expected)
    pd.testing.assert_frame_equal(pd.read_excel(tmp_path / 'summary/Analysis.xlsx'),
                                  expected, check_dtype=False)


@pytest.mark.parametrize('error_type', [OSError, ValueError, KeyError, TypeError, BadZipFile])
def test_read_errors_identify_input_and_preserve_cause(tmp_path, monkeypatch, error_type):
    failure = error_type('unreadable')
    def fail(path):
        raise failure
    monkeypatch.setattr(pd, 'read_excel', fail)
    selected = {'columns': ['p'], 'output': None}
    with pytest.raises(ValueError) as caught:
        analysis.analyze(selected, root=tmp_path, groups=[({'p': 1}, ['broken.xlsx'])])
    assert str(tmp_path / 'broken.xlsx') in str(caught.value)
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize('history', [
    {'Step': [1, 2], 'Result': [10, 'bad']},
    {'Step': [1, 'bad'], 'Result': [20, 10]},
])
def test_calculation_errors_identify_workbook(tmp_path, history):
    source = tmp_path / 'bad-history.xlsx'
    pd.DataFrame(history).to_excel(source, index=False)
    selected = {'columns': ['p'], 'output': None}
    with pytest.raises(ValueError) as caught:
        analysis.analyze(selected, groups=[({'p': 1}, [source])])
    assert str(source) in str(caught.value)
    assert isinstance(caught.value.__cause__, TypeError)


@pytest.mark.parametrize('result', [float('inf'), True, '12'])
def test_existing_excel_value_inference_is_preserved(tmp_path, result):
    source = tmp_path / 'history.xlsx'
    pd.DataFrame({'Step': [3], 'Result': [result]}).to_excel(source, index=False)
    selected = {'columns': ['p'], 'output': None}
    table = analysis.analyze(selected, groups=[({'p': 1}, [source])])
    expected = float(result)
    assert table['mean_minimum_result'].tolist() == [expected]
    assert table['best_result'].tolist() == [expected]
    assert table['mean_step_of_minimum'].tolist() == [3.]


def test_repetition_minima_have_equal_weight_despite_missing_samples(tmp_path):
    histories = (
        [[None, None], [7.5, 1.25], [9, 2.5]],
        [[2, 8], [4.5, 3.75], [8, 6], [10, 5]],
    )
    for number, history in enumerate(histories, 17):
        pd.DataFrame(history, columns=['Step', 'Result']).to_excel(
            tmp_path / f'{number}.xlsx', index=False)
    selected = {'columns': ['p'], 'output': None}

    table = analysis.analyze(selected, root=tmp_path, groups=[({'p': 1}, ['17.xlsx', '18.xlsx'])])

    # Each history contributes one minimum, regardless of its sample count.
    assert table['mean_minimum_result'].tolist() == [2.5]
    assert table['mean_step_of_minimum'].tolist() == [6.0]
    assert table['best_result'].tolist() == [1.25]


def test_missing_results_in_later_repetition_reject_entire_summary(tmp_path):
    pd.DataFrame({'Step': [1], 'Result': [10]}).to_excel(
        tmp_path / '1.xlsx', index=False)
    pd.DataFrame({'Step': [2, 3], 'Result': [None, None]}).to_excel(
        tmp_path / '2.xlsx', index=False)
    selected = {'columns': ['p'], 'output': 'Analysis.xlsx'}

    with pytest.raises(ValueError, match='does not contain valid results') as caught:
        analysis.analyze(selected, root=tmp_path, groups=[({'p': 1}, ['1.xlsx', '2.xlsx'])])

    assert str(tmp_path / '2.xlsx') in str(caught.value)
    assert not (tmp_path / 'Analysis.xlsx').exists()


@pytest.mark.parametrize('repetitions, expected_order, expected_mean', [
    ({'start': 17, 'stop': 20}, [17, 18, 19], 1 / 3),
    ({'start': 19, 'stop': 16, 'step': -1}, [19, 18, 17], 0.0),
])
def test_repetition_order_preserves_floating_point_summation(
        tmp_path, monkeypatch, repetitions, expected_order, expected_mean):
    # Synthetic values expose rounding differences hidden by integer examples.
    results = {17: 1e16, 18: -1e16, 19: 1.0}
    reads = []

    def read_history(path):
        number = int(path.stem)
        reads.append(number)
        return pd.DataFrame({'Step': [7.0], 'Result': [results[number]]})

    monkeypatch.setattr(pd, 'read_excel', read_history)
    selected = {'columns': ['p'], 'output': None}

    table = analysis.analyze(selected, root=tmp_path, groups=[
        ({'p': 1}, [f'{n}.xlsx' for n in range(
            repetitions['start'], repetitions['stop'], repetitions.get('step', 1))])])

    assert reads == expected_order
    assert table['mean_minimum_result'].tolist() == [expected_mean]
    assert table['mean_step_of_minimum'].tolist() == [7.0]
    assert table['best_result'].tolist() == [-1e16]


def test_opposite_infinite_minima_preserve_nan_mean(tmp_path):
    for number, result in enumerate((float('inf'), float('-inf')), 1):
        pd.DataFrame({'Step': [number], 'Result': [result]}).to_excel(
            tmp_path / f'{number}.xlsx', index=False)
    selected = {'columns': ['p'], 'output': None}

    with pytest.warns(RuntimeWarning, match='invalid value'):
        table = analysis.analyze(selected, root=tmp_path, groups=[({'p': 1}, ['1.xlsx', '2.xlsx'])])

    assert pd.isna(table.loc[0, 'mean_minimum_result'])
    assert table['mean_step_of_minimum'].tolist() == [1.5]
    assert table['best_result'].tolist() == [float('-inf')]


def test_explicit_paths_match_relative_files_columns_and_excel(tmp_path):
    definition = {'columns': ['operator'], 'output': 'relative.xlsx'}
    groups = []
    for operator in (3, 1):
        paths = []
        histories = (
            [[None, None], [7.5, operator + 1.25], [3, operator + 1.25]],
            [[2, operator + 8], [4.5, operator + 3.75], [8, operator + 6],
             [10, operator + 5]],
        )
        for number, history in enumerate(histories, 17):
            path = tmp_path / str(operator) / str(number) / 'history.xlsx'
            path.parent.mkdir(parents=True)
            pd.DataFrame(history, columns=['Step', 'Result']).to_excel(path, index=False)
            # Exercise absolute Paths and relative strings on the same files.
            paths.append(path if number == 17 else str(path.relative_to(tmp_path)))
        groups.append(({'operator': operator}, iter(paths)))

    expected = analysis.analyze(definition, root=tmp_path, groups=[
        ({'operator': op}, [f'{op}/{n}/history.xlsx' for n in (17, 18)]) for op in (3, 1)])
    actual = analysis.analyze({'columns': ['operator'], 'output': 'explicit.xlsx'},
                              root=tmp_path, groups=iter(groups))

    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    assert actual['operator'].tolist() == [3, 1]
    assert actual['mean_minimum_result'].tolist() == [5.5, 3.5]
    assert actual['mean_step_of_minimum'].tolist() == [6.0, 6.0]
    assert actual['best_result'].tolist() == [4.25, 2.25]
    pd.testing.assert_frame_equal(pd.read_excel(tmp_path / 'explicit.xlsx'),
                                  pd.read_excel(tmp_path / 'relative.xlsx'), check_exact=True)


@pytest.mark.parametrize('repetitions, order, mean', [
    ({'start': 17, 'stop': 20}, [17, 18, 19], 1 / 3),
    ({'start': 19, 'stop': 16, 'step': -1}, [19, 18, 17], 0.0),
])
def test_explicit_path_order_matches_relative_float_arithmetic(
        tmp_path, repetitions, order, mean):
    for number, result in ((17, 1e16), (18, -1e16), (19, 1.0)):
        # A missing sample keeps Excel inference floating-point, rather than int64.
        pd.DataFrame({'Step': [7, 9], 'Result': [result, None]}).to_excel(
            tmp_path / f'{number}.xlsx', index=False)
    definition = {'columns': ['p'], 'output': None}
    expected = analysis.analyze(definition, root=tmp_path, groups=[
        ({'p': 1}, [f'{n}.xlsx' for n in range(
            repetitions['start'], repetitions['stop'], repetitions.get('step', 1))])])
    actual = analysis.analyze({'columns': ['p'], 'output': None}, groups=[
        ({'p': 1}, [tmp_path / f'{number}.xlsx' for number in order])])
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    assert actual['mean_minimum_result'].tolist() == [mean]


def test_explicit_paths_preserve_infinities_and_nan_aggregation(tmp_path):
    paths = []
    for number, value in enumerate((float('inf'), float('-inf')), 1):
        path = tmp_path / f'{number}.xlsx'
        pd.DataFrame({'Step': [number], 'Result': [value]}).to_excel(path, index=False)
        paths.append(path)
    definition = {'columns': ['p'], 'output': None}
    with pytest.warns(RuntimeWarning, match='invalid value'):
        expected = analysis.analyze(definition, root=tmp_path, groups=[({'p': 1}, ['1.xlsx', '2.xlsx'])])
    with pytest.warns(RuntimeWarning, match='invalid value'):
        actual = analysis.analyze({'columns': ['p'], 'output': None},
                                  groups=[({'p': 1}, paths)])
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    assert pd.isna(actual.loc[0, 'mean_minimum_result'])
    assert actual['best_result'].tolist() == [float('-inf')]


def test_explicit_groups_keep_noncartesian_configurations_and_column_order(tmp_path):
    configurations = [
        {'operator': 10, 'k': 10, 'ring': True, 'permutation_reset': False},
        {'operator': 15, 'k': 5, 'ring': False, 'permutation_reset': True},
        {'operator': 15, 'k': 20, 'ring': True, 'permutation_reset': True},
    ]
    columns = ['ring', 'permutation_reset', 'operator', 'k']
    groups = []
    for number, configuration in enumerate(configurations, 1):
        path = tmp_path / f'{number}.xlsx'
        pd.DataFrame({'Step': [number], 'Result': [number * 10]}).to_excel(path, index=False)
        groups.append((configuration, [path]))
    actual = analysis.analyze({'columns': columns, 'output': None}, groups=groups)
    expected = pd.DataFrame([
        {**c, 'mean_minimum_result': float(i * 10), 'mean_step_of_minimum': float(i),
         'best_result': i * 10} for i, c in enumerate(configurations, 1)
    ], columns=columns + analysis.METRICS)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


@pytest.mark.parametrize('history, message', [
    ([], 'does not contain valid results'),
    ([[1, None], [2, None]], 'does not contain valid results'),
    ([[None, 1], [2, 1]], 'minimum result has no Step'),
])
def test_explicit_paths_preserve_history_errors(tmp_path, history, message):
    path = tmp_path / '1.xlsx'
    pd.DataFrame(history, columns=['Step', 'Result']).to_excel(path, index=False)
    definition = {'columns': ['p'], 'output': 'summary.xlsx'}
    with pytest.raises(ValueError, match=message) as relative:
        analysis.analyze(definition, root=tmp_path, groups=[({'p': 1}, ['1.xlsx'])])
    with pytest.raises(ValueError, match=message) as explicit:
        analysis.analyze({'columns': ['p'], 'output': 'summary.xlsx'}, root=tmp_path,
                         groups=[({'p': 1}, [path])])
    assert str(explicit.value) == str(relative.value)
    assert not (tmp_path / 'summary.xlsx').exists()


def test_explicit_group_requires_at_least_one_history(tmp_path):
    with pytest.raises(ValueError, match='repetition paths cannot be empty'):
        analysis.analyze({'columns': ['p'], 'output': 'summary.xlsx'}, root=tmp_path,
                         groups=[({'p': 1}, iter(()))])
    assert not (tmp_path / 'summary.xlsx').exists()


def test_empty_explicit_groups_preserve_columns():
    table = analysis.analyze({'columns': ['p'], 'output': None}, groups=[])
    assert table.empty
    assert table.columns.tolist() == ['p'] + analysis.METRICS
