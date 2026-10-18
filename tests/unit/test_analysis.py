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
