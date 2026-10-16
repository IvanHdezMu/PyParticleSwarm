"""The Excel writer consumes history without requiring a solver."""

import pandas as pd
import pytest

from tsp_pso.infrastructure.writers.excel_result_writer import ExcelResultWriter

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('history', [[], [[13, 8.5], [5, 9.25], [13, 7.0]]])
def test_excel_layout_and_row_order(tmp_path, history):
    destination = tmp_path / 'results.xlsx'
    original = [row.copy() for row in history]
    ExcelResultWriter().write(history, destination)
    actual = pd.read_excel(destination)
    expected = pd.DataFrame(history, columns=['Step', 'Result'])
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
    assert history == original


def test_excel_write_exception_propagates(monkeypatch, tmp_path):
    failure = OSError('cannot write workbook')

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(pd.DataFrame, 'to_excel', fail)
    with pytest.raises(OSError) as caught:
        ExcelResultWriter().write([[1, 2]], tmp_path / 'results.xlsx')
    assert caught.value is failure
