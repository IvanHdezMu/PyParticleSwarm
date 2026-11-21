"""Read real batch artifacts and Excel histories without executing a solver."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pandas as pd
import pytest

from tsp_pso.analysis.analysis import METRICS, analyze
from tsp_pso.analysis.analysis import prepare_batch_groups, BATCH_COLUMNS
from tsp_pso.experiments.experiment_config import RepetitionSpec

pytestmark = pytest.mark.functional


def _analyze_prepared(directory):
    return analyze({'columns': BATCH_COLUMNS, 'output': None},
                   groups=prepare_batch_groups(directory))


def contents(directory):
    return {p.relative_to(directory): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def test_moved_batch_is_read_only_and_independent_of_live_catalog(
        completed_batch, tmp_path, monkeypatch):
    directory = completed_batch(datasets=('z',), problem_modes=('tspwr',), particles=(4, 2))
    # A previous summary must never be mistaken for a raw history or overwritten.
    (directory / 'Analysis.xlsx').write_bytes(b'previous summary')
    for path in directory.rglob('run_config.json'):
        pd.DataFrame({'Step': [1], 'Result': [-999]}).to_excel(
            path.parent / 'Analysis_sample.xlsx', index=False)
    moved = tmp_path / 'elsewhere' / 'renamed-batch'
    moved.parent.mkdir()
    shutil.move(str(directory), moved)
    before = contents(moved)

    def forbidden(*args, **kwargs):
        raise AssertionError('Analysis must not load datasets or regenerate runs')

    monkeypatch.setattr('tsp_pso.experiments.experiment_batch.load_catalog', forbidden)
    monkeypatch.setattr('tsp_pso.experiments.experiment_batch.iterate_runs', forbidden)
    monkeypatch.setattr('tsp_pso.infrastructure.dataset_reader.load_dataset', forbidden)
    monkeypatch.setattr('tsp_pso.application.runner.execute', forbidden)
    monkeypatch.chdir(tmp_path)
    table = _analyze_prepared(moved.relative_to(tmp_path))

    assert list(zip(table.dataset, table.problem_mode, table.particles)) == [
        ('z', 'tspwr', n) for n in (4, 2)]
    assert table['mean_minimum_result'].tolist() == [27.5] * 2
    assert contents(moved) == before


@pytest.mark.parametrize('style', ['standard', 'berlin_grid', 'bays', 'fuel'])
def test_batch_statistics_equal_traditional_analysis_on_same_histories(
        completed_batch, tmp_path, style):
    histories = {
        17: [[None, None], [7.5, 1.25], [3, 1.25]],
        18: [[9, 20], [4.5, 3.75], [2, 10]],
    }
    directory = completed_batch(legacy_style=style, history=lambda r: histories[r.repetition_id])
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        records = db.execute('SELECT configuration,output FROM runs').fetchall()
    flat = tmp_path / 'traditional'
    flat.mkdir()
    for payload, output in records:
        repetition = json.loads(payload)['repetition_id']
        source, = Path(output).glob('*.xlsx')
        shutil.copyfile(source, flat / f'{repetition}.xlsx')
    traditional = analyze({
        'parameters': {'p': [1]}, 'columns': ['p'],
        'repetitions': {'start': 17, 'stop': 19},
        'input_template': str(flat / '{number}.xlsx'), 'output': None,
    })
    actual = _analyze_prepared(directory)
    pd.testing.assert_frame_equal(actual[METRICS], traditional[METRICS], check_exact=True)
    assert not (directory / 'Analysis.xlsx').exists()


def test_repetitions_are_summed_by_id_not_manifest_ordinal(completed_batch):
    values = {17: 1e16, 18: -1e16, 19: 1.0}
    directory = completed_batch(repetitions=RepetitionSpec(3, 17),
                                history=lambda r: [[7, values[r.repetition_id]]])
    # Persist the same group with its final repetition appearing first.
    order = (3, 1, 2)
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        records = {int(o): (config, Path(path)) for o, config, path in db.execute(
            'SELECT ordinal,configuration,output FROM runs')}
        staging = directory / 'reorder'
        (directory / 'runs').rename(staging)
        for ordinal, previous in enumerate(order, 1):
            config, path = records[previous]
            target = directory / 'runs' / str(ordinal)
            target.parent.mkdir(exist_ok=True)
            (staging / str(previous)).rename(target)
            relocated = target / path.relative_to(directory / 'runs' / str(previous))
            db.execute('UPDATE runs SET configuration=?,output=? WHERE ordinal=?',
                       (config, str(relocated), str(ordinal)))
        staging.rmdir()
    table = _analyze_prepared(directory)
    assert table['mean_minimum_result'].tolist() == [1 / 3]
    assert table['mean_step_of_minimum'].tolist() == [7.0]
    assert table['best_result'].tolist() == [-1e16]


def test_opposite_infinities_retain_existing_statistics(completed_batch):
    directory = completed_batch(history=lambda r: [[1, float('inf') if r.repetition_id == 17
                                                   else float('-inf')]])
    with pytest.warns(RuntimeWarning, match='invalid value'):
        table = _analyze_prepared(directory)
    assert pd.isna(table.loc[0, 'mean_minimum_result'])
    assert table['best_result'].tolist() == [float('-inf')]
    assert table['mean_step_of_minimum'].tolist() == [1.0]
