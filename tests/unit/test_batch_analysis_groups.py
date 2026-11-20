"""Batch identity, grouping and all-or-nothing input validation."""
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from tsp_pso.analysis.analysis import analyze, prepare_batch_groups, BATCH_COLUMNS

pytestmark = pytest.mark.unit


def _analyze_prepared(directory):
    return analyze({'columns': BATCH_COLUMNS, 'output': None},
                   groups=prepare_batch_groups(directory))


def edit_json(path, change):
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))


def edit_run(directory, change, ordinal='1'):
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        value = json.loads(db.execute('SELECT configuration FROM runs WHERE ordinal=?',
                                      (ordinal,)).fetchone()[0])
        change(value)
        db.execute('UPDATE runs SET configuration=? WHERE ordinal=?',
                   (json.dumps(value), ordinal))


def output(directory, ordinal=1):
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        return Path(db.execute('SELECT output FROM runs WHERE ordinal=?',
                               (str(ordinal),)).fetchone()[0])


def test_group_order_numeric_ordinals_and_effective_columns(completed_batch):
    directory = completed_batch(c1=(9, 7, 5, 3, 2, 1), permutation_reset=(False,),
                                k=(4, 8), reset_threshold_divisor=(250,))
    table = _analyze_prepared(directory)
    assert list(table.columns) == [
        'dataset', 'problem_mode', 'particles', 'c1', 'operator',
        'ring', 'permutation_reset', 'k',
        'primary_operator_share', 'minimum_reset_probability',
        'maximum_reset_probability', 'reset_threshold_divisor', 'progress_warmup_multiplier',
        'fuel_capacity', 'consumption', 'full_initial_tank', 'repetitions', 'inactive_parameters', 'mean_minimum_result',
        'mean_step_of_minimum', 'best_result',
    ]
    assert table['c1'].tolist() == [9, 7, 5, 3, 2, 1]
    assert table['repetitions'].tolist() == [2] * 6
    assert table['mean_minimum_result'].tolist() == [27.5] * 6
    assert table['mean_step_of_minimum'].tolist() == [7.0] * 6
    assert table['best_result'].tolist() == [27] * 6
    assert table['k'].tolist() == [10] * 6
    assert table['reset_threshold_divisor'].tolist() == [250] * 6
    assert all('reset_threshold_divisor' in text for text in table['inactive_parameters'])


def test_effective_reset_divisors_and_warmup_remain_separate(completed_batch):
    directory = completed_batch(reset_threshold_divisor=(250, 1000),
                                progress_warmup_multiplier=(0, 5))
    table = _analyze_prepared(directory)
    assert list(zip(table.reset_threshold_divisor, table.progress_warmup_multiplier)) == [
        (250, 0), (250, 5), (1000, 0), (1000, 5)]


def test_persisted_inactive_multivalue_fallback_is_not_replaced(completed_batch, monkeypatch):
    from tsp_pso.experiments import experiment_batch
    directory = completed_batch(permutation_reset=(False,), reset_threshold_divisor=(2, 3))
    for ordinal in ('1', '2'):
        edit_run(directory, lambda r: r['legacy_values'].update(reset_threshold_divisor=321), ordinal)
        edit_json(output(directory, ordinal) / 'run_config.json',
                  lambda r: r.update(reset_threshold_divisor=321))
    monkeypatch.setitem(experiment_batch.DEFAULTS, 'reset_threshold_divisor', 999)
    assert _analyze_prepared(directory)['reset_threshold_divisor'].tolist() == [321]


def test_presentation_metadata_does_not_split_repetitions(completed_batch):
    directory = completed_batch()
    edit_run(directory, lambda r: r.update(name='Other display name', legacy_label='Other label',
                                           output_dir='/obsolete/requested/root'), '2')
    assert len(_analyze_prepared(directory)) == 1


@pytest.mark.parametrize('target', ['batch.json', 'manifest.sqlite3'])
@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_missing_or_invalid_batch_files(completed_batch, target, damage):
    directory = completed_batch()
    path = directory / target
    if damage == 'missing':
        path.unlink()
    else:
        path.write_text('invalid')
    with pytest.raises(ValueError, match='Batch'):
        _analyze_prepared(directory)
    if damage == 'missing':
        assert not path.exists()


@pytest.mark.parametrize('change, message', [
    (lambda s: s.update(batch_id='different'), 'identifier mismatch'),
    (lambda s: s.update(expansion_version=2), 'Unsupported expansion'),
    (lambda s: s.update(expansion_version=True), 'Unsupported expansion'),
    (lambda s: s.update(total_runs='3'), 'Declared total'),
    (lambda s: s['configuration'].pop('repetitions'), 'configuration'),
    (lambda s: s['configuration']['repetitions'].update(first_id=18), 'repetition_id'),
    (lambda s: s.update(datasets=[]), 'Unknown dataset'),
    (lambda s: s['datasets'][0].update(problem_types='tsp'), 'dataset descriptor'),
])
def test_invalid_batch_snapshot(completed_batch, change, message):
    directory = completed_batch()
    edit_json(directory / 'batch.json', change)
    with pytest.raises(ValueError, match=message):
        _analyze_prepared(directory)


@pytest.mark.parametrize('scope', ['batch', 'runs'])
@pytest.mark.parametrize('status', ['pending', 'running', 'failed', 'interrupted'])
def test_unsuccessful_states_are_rejected(completed_batch, scope, status):
    directory = completed_batch()
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        db.execute(f'UPDATE {scope} SET status=?', (status,))
    with pytest.raises(ValueError, match='status'):
        _analyze_prepared(directory)


@pytest.mark.parametrize('statement, message', [
    ("UPDATE batch SET total='3'", 'Declared totals'),
    ("DELETE FROM runs WHERE ordinal='2'", 'Incomplete batch'),
    ("UPDATE runs SET ordinal='3' WHERE ordinal='2'", 'ordinal'),
    ("UPDATE runs SET ordinal='01' WHERE ordinal='1'", 'ordinal'),
    ("UPDATE runs SET run_id='other' WHERE ordinal='1'", 'run_id'),
    ("UPDATE runs SET output=NULL WHERE ordinal='1'", 'Missing output'),
    ("UPDATE runs SET output='/old/runs/9/sample/dir' WHERE ordinal='1'", 'layout'),
    ("UPDATE runs SET ended_at=NULL WHERE ordinal='1'", 'completion'),
    ("UPDATE runs SET configuration='invalid' WHERE ordinal='1'", 'Run 1'),
    ("DROP TABLE runs", 'runs'),
    ("ALTER TABLE batch DROP COLUMN status", 'status'),
])
def test_manifest_inconsistencies(completed_batch, statement, message):
    directory = completed_batch()
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        db.execute(statement)
    with pytest.raises(ValueError, match=message):
        _analyze_prepared(directory)


@pytest.mark.parametrize('change, message', [
    (lambda r: r.update(particles=99), 'saved request'),
    (lambda r: r.update(operator=True), 'Unsupported operator'),
    (lambda r: r.update(repetition_id=0), 'first_id'),
    (lambda r: r.update(repetition_id=100), 'Unexpected repetition'),
    (lambda r: r.update(repetition_id=17), 'Duplicate repetition'),
    (lambda r: r.update(excel=False), 'excel'),
    (lambda r: r.update(k=10), 'Inactive expansion'),
    (lambda r: r.update(minimum_reset_probability=0.3), 'active parameter'),
    (lambda r: r.update(progress_warmup_multiplier=[]), 'active parameter'),
    (lambda r: r['legacy_values'].pop('k'), 'nine effective'),
    (lambda r: r['legacy_values'].update(reset_threshold_divisor=None), 'finite'),
    (lambda r: r['legacy_values'].update(k=11), 'Inactive singleton'),
    (lambda r: r.pop('verbose'), 'concrete configuration'),
])
def test_invalid_concrete_configurations(completed_batch, change, message):
    directory = completed_batch()
    edit_run(directory, change, '2')
    with pytest.raises(ValueError, match=message):
        _analyze_prepared(directory)


def test_missing_repetition_inside_group_with_unchanged_total(completed_batch):
    directory = completed_batch(permutation_reset=(False,), reset_threshold_divisor=(2, 3))
    edit_run(directory, lambda r: r['legacy_values'].update(reset_threshold_divisor=500), '2')
    edit_json(output(directory, 2) / 'run_config.json',
              lambda s: s.update(reset_threshold_divisor=500))
    with pytest.raises(ValueError, match='Inconsistent effective values'):
        _analyze_prepared(directory)


@pytest.mark.parametrize('field, value', [
    ('dataset', 'other'), ('steps', [99]), ('refuel', True),
    ('repetitions', {'start': 18, 'stop': 19, 'step': 1}),
    ('reset_threshold_divisor', 1), ('full_tanks', [True]), ('rings', [1]),
])
def test_run_snapshot_identity(completed_batch, field, value):
    directory = completed_batch()
    edit_json(output(directory) / 'run_config.json', lambda s: s.update({field: value}))
    with pytest.raises(ValueError, match=f'inconsistent {field}'):
        _analyze_prepared(directory)


@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_missing_or_corrupt_run_snapshot(completed_batch, damage):
    directory = completed_batch()
    path = output(directory) / 'run_config.json'
    if damage == 'missing':
        path.unlink()
    else:
        path.write_text('invalid')
    with pytest.raises(ValueError, match='Run 1'):
        _analyze_prepared(directory)


@pytest.mark.parametrize('damage', ['missing', 'empty', 'corrupt', 'all_missing', 'columns', 'step'])
def test_bad_histories_reject_whole_batch(completed_batch, damage):
    directory = completed_batch()
    path, = output(directory, 2).glob('*.xlsx')
    if damage == 'missing':
        path.unlink()
    elif damage == 'corrupt':
        path.write_bytes(b'not Excel')
    else:
        frames = {
            'empty': pd.DataFrame(columns=['Step', 'Result']),
            'all_missing': pd.DataFrame({'Step': [1], 'Result': [None]}),
            'columns': pd.DataFrame({'Other': [1]}),
            'step': pd.DataFrame({'Step': [None], 'Result': [1]}),
        }
        frames[damage].to_excel(path, index=False)
    with pytest.raises(ValueError):
        _analyze_prepared(directory)
    assert not (directory / 'Analysis.xlsx').exists()


def test_excel_disabled_is_rejected(completed_batch):
    directory = completed_batch(excel=False)
    with pytest.raises(ValueError, match='excel=False'):
        _analyze_prepared(directory)


def test_duplicate_ordinals_in_malformed_manifest(completed_batch):
    directory = completed_batch()
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        db.execute('ALTER TABLE runs RENAME TO original_runs')
        db.execute('CREATE TABLE runs AS SELECT * FROM original_runs')
        db.execute("UPDATE runs SET ordinal='1' WHERE ordinal='2'")
    with pytest.raises(ValueError, match='ordinal'):
        _analyze_prepared(directory)


def test_complete_missing_configuration_cannot_be_replaced_by_other_fallback(completed_batch):
    directory = completed_batch(c1=(2, 3), permutation_reset=(False,),
                                reset_threshold_divisor=(2, 3))
    for ordinal in ('3', '4'):
        def change(run):
            run['c1'] = 2
            run['legacy_values']['reset_threshold_divisor'] = 500
        edit_run(directory, change, ordinal)
        edit_json(output(directory, ordinal) / 'run_config.json',
                  lambda s: s.update(steps=[2], reset_threshold_divisor=500))
    with pytest.raises(ValueError, match='Inconsistent effective values'):
        _analyze_prepared(directory)


def test_conditional_operator_axes_use_saved_scalars(completed_batch):
    directory = completed_batch(operators=(10, 15), k=(1000, 2000),
                                primary_operator_share=(0.2, 0.8))
    table = _analyze_prepared(directory)
    assert list(zip(table.operator, table.k, table.primary_operator_share)) == [
        (10, 10, 0.2), (15, 1000, 0.2), (15, 1000, 0.8),
        (15, 2000, 0.2), (15, 2000, 0.8),
    ]
    assert 'k' in table.loc[0, 'inactive_parameters'].split(', ')
    assert all('k' not in text.split(', ') for text in table.inactive_parameters[1:])


@pytest.mark.parametrize('selection', [
    {'datasets': ('sample', 'other')}, {'problem_modes': ('tsp', 'tspwr')},
])
def test_multiselection_api_batches_are_rejected(completed_batch, selection):
    directory = completed_batch(**selection)
    with pytest.raises(ValueError, match='exactly one dataset and one problem mode'):
        prepare_batch_groups(directory)


def test_ring_reset_and_conditional_groups_are_explicit(completed_batch):
    directory = completed_batch(ring=(True, False), permutation_reset=(False, True),
                                reset_threshold_divisor=(250, 1000))
    groups = prepare_batch_groups(directory)
    assert [(row['permutation_reset'], row['ring'], row['reset_threshold_divisor'])
            for row, paths in groups] == [
        (False, True, 1000), (False, False, 1000),
        (True, True, 250), (True, True, 1000), (True, False, 250), (True, False, 1000)]
    assert all(len(paths) == 2 for row, paths in groups)
