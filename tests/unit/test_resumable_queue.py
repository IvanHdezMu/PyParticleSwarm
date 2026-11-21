"""Materialized queues preserve effective inputs without re-expansion."""
import json
from unittest.mock import Mock

import pytest

from tsp_pso.experiments import batch_store as store
from tsp_pso.experiments.experiment_batch import compile_plan, iterate_runs
from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)


def test_queue_has_original_order_and_effective_values(tmp_path, monkeypatch):
    plan = compile_plan(ExperimentConfiguration(datasets=('bays29',), operators=(10,15),
        k=(3,7), permutation_reset=(False,), reset_threshold_divisor=(321,17),
        repetitions=RepetitionSpec(2,23), output_dir=tmp_path))
    expected = [r.to_dict() for r in iterate_runs(plan)]
    directory = store.create_batch(plan)
    monkeypatch.setattr(store, 'iterate_runs', Mock(side_effect=AssertionError('expansion')))
    monkeypatch.setattr(store, 'count_runs', Mock(side_effect=AssertionError('count expansion')))
    _, batch, rows = store.read_batch(directory)
    assert batch['manifest_version'] == 2
    assert [json.loads(r['configuration']) for r in rows] == expected
    assert all(r['status']=='pending' and r['started_at'] is None for r in rows)
    assert [r['repetition_id'] for r in expected] == [23,24,23,24,23,24]
    assert all(r['legacy_values']['reset_threshold_divisor']==1000 for r in expected)


def test_preparation_failure_never_publishes_partial_batch(tmp_path, monkeypatch):
    plan = compile_plan(ExperimentConfiguration(datasets=('bays29',), output_dir=tmp_path))
    def broken(plan):
        yield next(iterate_runs(plan))
        raise OSError('disk failure')
    monkeypatch.setattr(store, 'iterate_runs', broken)
    with pytest.raises(OSError, match='disk failure'):
        store.create_batch(plan)
    assert list((tmp_path/'batches').iterdir()) == []


def test_recovery_uses_saved_runs_without_repeating_success(batch_artifacts, monkeypatch):
    from tsp_pso.experiments import experiment_batch
    from tsp_pso.experiments.batch_executor import execute_batch
    directory, write = batch_artifacts(completed=False)
    calls = []
    def interrupt(run, output, descriptor):
        calls.append(run.repetition_id)
        if run.repetition_id == 18:
            raise KeyboardInterrupt
        return write(run, output, descriptor)
    execute_batch(directory, interrupt)
    _, _, before = store.read_batch(directory)
    first = before[0].copy()
    artifacts = {p: p.read_bytes() for p in (directory/'runs/1').rglob('*') if p.is_file()}
    monkeypatch.setattr(experiment_batch, 'iterate_runs', Mock(side_effect=AssertionError('re-expansion')))
    monkeypatch.setattr(store, 'count_runs', Mock(side_effect=AssertionError('re-count')))
    monkeypatch.setitem(experiment_batch.DEFAULTS, 'k', 999)
    execute_batch(directory, lambda r,p,d: (calls.append(r.repetition_id),write(r,p,d))[1])
    assert calls == [17,18,18]
    assert store.read_batch(directory)[2][0] == first
    assert all(p.read_bytes()==content for p,content in artifacts.items())
    assert store.batch_status(directory)['status'] == 'succeeded'
    assert (directory/'Analysis.xlsx').is_file()


def test_os_lock_rejects_second_owner(batch_artifacts):
    from tsp_pso.experiments.experiment_process import execution_lock
    directory, _ = batch_artifacts(completed=False)
    with (execution_lock(directory), pytest.raises(ValueError, match='active coordinator'),
          execution_lock(directory)):
        pytest.fail('Second coordinator acquired lock')


def test_live_previous_group_blocks_recovery(batch_artifacts):
    import subprocess
    import sys
    from pathlib import Path

    from tsp_pso.experiments.experiment_process import execution_lock
    directory, _ = batch_artifacts(completed=False)
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    try:
        owner = {'pid': child.pid, 'pgid': child.pid,
                 'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        with store.connect(directory) as db:
            db.execute('UPDATE control SET owner=?', (json.dumps(owner),))
        with pytest.raises(ValueError, match='still alive'), execution_lock(directory):
            pytest.fail('Recovered while previous process group was alive')
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_pause_commits_current_run_before_stopping(batch_artifacts):
    from tsp_pso.experiments.batch_executor import execute_batch
    directory, write = batch_artifacts(completed=False)
    calls = []
    def run(config, path, descriptor):
        calls.append(config.repetition_id)
        store.request_pause(directory)
        assert store.batch_status(directory)['status'] == 'running'
        return write(config, path, descriptor)
    execute_batch(directory, run)
    state = store.batch_status(directory)
    assert state['status'] == 'paused' and state['counts']['succeeded'] == 1
    assert state['counts']['pending'] == 1
    assert not (directory/'Analysis.xlsx').exists()
    before = store.read_batch(directory)[2][0]
    execute_batch(directory, write)
    assert calls == [17]
    assert store.read_batch(directory)[2][0] == before
    assert store.batch_status(directory)['status'] == 'succeeded'
    assert (directory/'Analysis.xlsx').is_file()


def test_pause_before_first_run_and_last_run_completion(batch_artifacts):
    from tsp_pso.experiments.batch_executor import execute_batch
    directory, write = batch_artifacts(completed=False)
    store.request_pause(directory)
    execute_batch(directory, Mock(side_effect=AssertionError('run started')))
    assert store.batch_status(directory)['status'] == 'paused'
    def run(config,path,descriptor):
        if config.repetition_id == 18:
            store.request_pause(directory)
        return write(config,path,descriptor)
    execute_batch(directory, run)
    assert store.batch_status(directory)['status'] == 'succeeded'
    assert (directory/'Analysis.xlsx').exists()
