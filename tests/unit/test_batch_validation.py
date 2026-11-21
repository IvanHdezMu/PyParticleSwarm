"""Version-one persistence and validation before any scientific execution."""
import json
import sqlite3
from unittest.mock import Mock

import pytest

from tsp_pso.analysis.analysis import prepare_batch_groups
from tsp_pso.experiments.batch_executor import execute_batch


def test_current_version_one_artifacts_remain_readable(completed_batch):
    directory = completed_batch()
    snapshot = json.loads((directory / 'batch.json').read_text())
    assert snapshot['expansion_version'] == 1
    assert snapshot['total_runs'] == '2'
    assert snapshot['configuration']['repetitions'] == {'count': 2, 'first_id': 17}
    assert set(snapshot['configuration']) == {
        'datasets', 'name', 'problem_modes', 'particles', 'c1', 'operators', 'k',
        'ring', 'permutation_reset', 'minimum_reset_probability', 'maximum_reset_probability',
        'fuel_capacity', 'consumption', 'full_initial_tank', 'reset_threshold_divisor',
        'primary_operator_share', 'progress_warmup_multiplier', 'repetitions', 'verbose',
        'excel', 'output_dir', 'legacy_style', 'legacy_label', 'analysis_output'}
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        assert db.execute('SELECT id,total,status FROM batch').fetchone() == (
            snapshot['batch_id'], '2', 'succeeded')
        rows = db.execute('SELECT ordinal,configuration,output FROM runs ORDER BY ordinal').fetchall()
    assert [row[0] for row in rows] == ['1', '2']
    assert [json.loads(row[1])['repetition_id'] for row in rows] == [17, 18]
    before = {p: p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    groups = prepare_batch_groups(directory)
    assert len(groups) == 1 and len(groups[0][1]) == 2
    assert all(p.read_bytes() == content for p, content in before.items())


def test_pending_version_one_batch_executes(batch_artifacts):
    directory, write = batch_artifacts(completed=False)
    snapshot = (directory / 'batch.json').read_bytes()
    execute_batch(directory, write)
    assert (directory / 'batch.json').read_bytes() == snapshot
    assert (directory / 'Analysis.xlsx').is_file()
    assert len(prepare_batch_groups(directory)) == 1


@pytest.mark.parametrize('damage', [
    'boolean_version', 'float_version', 'unknown_version', 'numeric_total', 'padded_total',
    'wrong_total', 'missing_field', 'unknown_field', 'invalid_parameter', 'duplicate_dataset',
    'json_identity', 'sqlite_identity', 'sqlite_total', 'created_at', 'invalid_catalog',
    'pending_timestamp', 'pending_run', 'missing_manifest', 'missing_json', 'bad_schema',
])
def test_invalid_batch_rejected_before_any_run(batch_artifacts, damage):
    directory, _ = batch_artifacts(completed=False)
    path = directory / 'batch.json'
    data = json.loads(path.read_text())
    if damage == 'boolean_version': data['expansion_version'] = True
    elif damage == 'float_version': data['expansion_version'] = 1.0
    elif damage == 'unknown_version': data['expansion_version'] = 2
    elif damage == 'numeric_total': data['total_runs'] = 2
    elif damage == 'padded_total': data['total_runs'] = '02'
    elif damage == 'wrong_total': data['total_runs'] = '3'
    elif damage == 'missing_field': del data['configuration']['k']
    elif damage == 'unknown_field': data['configuration']['obsolete'] = 1
    elif damage == 'invalid_parameter': data['configuration']['particles'] = [True]
    elif damage == 'duplicate_dataset': data['datasets'] *= 2
    elif damage == 'json_identity': data['batch_id'] = 'other'
    elif damage == 'invalid_catalog': data['datasets'][0]['problem_types'] = ['unknown']
    path.write_text(json.dumps(data))
    with sqlite3.connect(directory / 'manifest.sqlite3') as db:
        if damage == 'sqlite_identity': db.execute("UPDATE batch SET id='other'")
        elif damage == 'sqlite_total': db.execute("UPDATE batch SET total='3'")
        elif damage == 'created_at': db.execute("UPDATE batch SET created_at='other'")
        elif damage == 'pending_timestamp': db.execute("UPDATE batch SET started_at='already started'")
        elif damage == 'pending_run': db.execute("INSERT INTO runs VALUES('1','id-1','running','{}','now',NULL,NULL,NULL)")
        elif damage == 'bad_schema': db.execute('DROP TABLE runs')
    if damage == 'missing_manifest': (directory / 'manifest.sqlite3').unlink()
    if damage == 'missing_json': path.unlink()
    execute = Mock(side_effect=AssertionError('solver must not run'))
    with pytest.raises((ValueError, OSError, sqlite3.Error)):
        execute_batch(directory, execute)
    execute.assert_not_called()
    assert not (directory / 'runs').exists()
    assert not (directory / 'Analysis.xlsx').exists()
    if damage == 'missing_manifest': assert not (directory / 'manifest.sqlite3').exists()
