"""Publication uses the original analyzer and never replaces a good file on failure."""
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from tsp_pso.analysis import analysis as module


def test_workbook_layout_and_original_calculations(completed_batch, monkeypatch):
    directory = completed_batch(particles=(2, 4), ring=(False, True))
    groups = module.prepare_batch_groups(directory)
    expected = module.analyze({'columns': module.BATCH_COLUMNS, 'output': None}, groups=groups)
    original = module.analyze
    calls = []

    def spy(*args, **kwargs):
        calls.append(kwargs['groups'])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, 'analyze', spy)
    raw = {p: p.read_bytes() for p in directory.rglob('*.xlsx')}
    output = module.analyze_batch(directory)
    assert output == directory / 'Analysis.xlsx'
    assert calls == [groups]
    pd.testing.assert_frame_equal(pd.read_excel(output), expected, check_dtype=False)
    workbook = load_workbook(output)
    assert workbook.sheetnames == ['Analysis']
    sheet = workbook['Analysis']
    assert sheet.freeze_panes == 'A2'
    assert sheet.auto_filter.ref == 'A1:U5'
    assert list(next(sheet.values)) == module.BATCH_COLUMNS + module.METRICS
    workbook.close()
    assert all(p.read_bytes() == content for p, content in raw.items())
    assert not list(directory.glob('.analysis-*'))


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'empty', 'write', 'format', 'publish'])
def test_failure_preserves_previous_summary(completed_batch, monkeypatch, existing, failure):
    directory = completed_batch()
    output = directory / 'Analysis.xlsx'
    if existing:
        output.write_bytes(b'previous summary')
    last = module.prepare_batch_groups(directory)[0][1][-1]
    if failure == 'missing':
        last.unlink()
    elif failure == 'corrupt':
        last.write_bytes(b'not Excel')
    elif failure == 'empty':
        pd.DataFrame(columns=['Step', 'Result']).to_excel(last, index=False)
    else:
        def fail(*args, **kwargs):
            raise OSError('publication test')
        if failure == 'write':
            monkeypatch.setattr(pd.DataFrame, 'to_excel', fail)
        elif failure == 'format':
            from openpyxl.workbook.workbook import Workbook
            monkeypatch.setattr(Workbook, 'save', fail)
        else:
            monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises((ValueError, OSError)):
        module.analyze_batch(directory)
    assert output.exists() == existing
    if existing:
        assert output.read_bytes() == b'previous summary'
    assert not list(directory.glob('.analysis-*'))


def test_relative_directory_uses_current_working_directory(completed_batch, monkeypatch):
    directory = completed_batch()
    monkeypatch.chdir(directory.parent)
    assert module.analyze_batch(directory.name) == directory / 'Analysis.xlsx'
