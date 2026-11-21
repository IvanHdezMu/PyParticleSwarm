"""Analysis path and numeric contracts using explicit Excel groups."""
import pandas as pd
import pytest

from tsp_pso.analysis import analysis

pytestmark = pytest.mark.functional


def test_explicit_absolute_paths_ignore_working_directory(tmp_path, monkeypatch):
    source = tmp_path / 'history.xlsx'
    destination = tmp_path / 'historical-summary.xlsx'
    pd.DataFrame({'Step': [7], 'Result': [12]}).to_excel(source, index=False)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    result = analysis.analyze({'columns': ['optType'], 'output': str(destination)}, root=elsewhere,
                              groups=[({'optType': 1}, [source])])
    pd.testing.assert_frame_equal(pd.read_excel(destination), result, check_dtype=False)
    assert list(elsewhere.iterdir()) == []


def test_multiple_operators_keep_original_summary_values(tmp_path):
    groups = []
    for operator in range(1, 6):
        paths = []
        for number in range(1, 11):
            path = tmp_path / f'{operator}_{number}.xlsx'
            pd.DataFrame({'Step': [1], 'Result': [operator * 10 + number]}).to_excel(path, index=False)
            paths.append(path)
        groups.append(({'optType': operator}, paths))
    result = analysis.analyze({'columns': ['optType'], 'output': None}, groups=groups)
    assert result['optType'].tolist() == [1, 2, 3, 4, 5]
    assert result['mean_minimum_result'].tolist() == [15.5, 25.5, 35.5, 45.5, 55.5]


@pytest.mark.parametrize('repetitions', [range(1, 6, 2), range(5, 0, -2), range(2, 5)])
def test_nonconsecutive_repetitions_preserve_statistics(tmp_path, repetitions):
    paths = []
    for count, number in enumerate(repetitions, 1):
        path = tmp_path / f'{number}.xlsx'
        pd.DataFrame({'Step': [5, 13], 'Result': [100 + count, 10 + count]}).to_excel(path, index=False)
        paths.append(path)
    result = analysis.analyze({'columns': ['p'], 'output': None}, groups=[({'p': 1}, paths)])
    assert result['mean_minimum_result'].tolist() == [12.]
    assert result['mean_step_of_minimum'].tolist() == [13.]
    assert result['best_result'].tolist() == [11]


def test_analysis_keeps_run_groups_separate(tmp_path):
    groups = []
    for run in (1, 2):
        paths = []
        for repetition in (1, 2):
            count = (run - 1) * 2 + repetition
            path = tmp_path / f'{run}_{repetition}.xlsx'
            pd.DataFrame({'Step': [5, 13], 'Result': [100 + count, 10 + count]}).to_excel(
                path, index=False)
            paths.append(path)
        groups.append(({'run': run}, paths))
    result = analysis.analyze({'columns': ['run'], 'output': 'Analysis.xlsx'},
                              root=tmp_path, groups=groups)
    assert result['mean_minimum_result'].tolist() == [11.5, 13.5]
    pd.testing.assert_frame_equal(pd.read_excel(tmp_path / 'Analysis.xlsx'),
                                  result, check_dtype=False)
