"""Per-call SQLite waits and real contention during GUI monitoring, without Tk."""
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock
import sqlite3

import pytest

from tsp_pso.experiments import batch_store as store, experiment_process as process_module
from tsp_pso.experiments.experiment_batch import compile_plan, iterate_runs
from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec
from tsp_pso.presentation import experiment_gui as gui

pytestmark = pytest.mark.unit


@pytest.fixture
def batch(tmp_path):
    plan = compile_plan(ExperimentConfiguration(
        datasets=('berlin52',), repetitions=RepetitionSpec(3), output_dir=tmp_path))
    directory = store.create_batch(plan)
    runs = iter(iterate_runs(plan))
    store.start_batch(directory)
    store.start_run(directory, 1, next(runs))
    store.finish_run(directory, 1, 'succeeded', output=tmp_path / 'completed')
    store.start_run(directory, 2, next(runs))
    return directory


def saved_rows(directory):
    with store.connect(directory) as db:
        return (tuple(tuple(row) for row in db.execute('SELECT * FROM batch')),
                tuple(tuple(row) for row in db.execute('SELECT * FROM runs ORDER BY ordinal')))


def process(directory, code):
    result = process_module.BatchProcess.__new__(process_module.BatchProcess)
    result.directory = directory
    result.interrupt_started = None
    result.process = Mock()
    result.process.poll.return_value = code
    return result


@pytest.mark.parametrize('options, milliseconds', [({}, 10000), ({'timeout': 0.05}, 50)])
def test_connection_timeout_is_per_call(batch, options, milliseconds):
    with store.connect(batch, **options) as db:
        assert db.execute('PRAGMA busy_timeout').fetchone()[0] == milliseconds
    with store.connect(batch) as db:
        assert db.execute('PRAGMA busy_timeout').fetchone()[0] == 10000
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'


@pytest.mark.parametrize('options, expected', [({}, 10), ({'timeout': 0.05}, 0.05)])
def test_status_and_reconciliation_forward_timeout(batch, monkeypatch, options, expected):
    original = store.sqlite3.connect
    connect = Mock(wraps=original)
    monkeypatch.setattr(store.sqlite3, 'connect', connect)
    store.batch_status(batch, **options)
    assert connect.call_args.kwargs['timeout'] == expected
    store.mark_interrupted(batch, 'test', **options)
    assert connect.call_args.kwargs['timeout'] == expected
    # An ordinary executor write still uses ten seconds after a short call.
    store.finish_batch(batch, 'interrupted')
    assert connect.call_args.kwargs['timeout'] == 10


@pytest.mark.parametrize('options, expected', [({}, 10), ({'sqlite_timeout': 0.05}, 0.05)])
def test_process_forwards_timeout_to_read_and_reconciliation(monkeypatch, options, expected):
    directory = Path('batch')
    child = process(directory, 7)
    status = Mock(return_value={'status': 'running'})
    mark = Mock()
    monkeypatch.setattr(process_module, 'batch_status', status)
    monkeypatch.setattr(process_module, 'mark_interrupted', mark)
    assert child.poll(**options) == 7
    status.assert_called_once_with(directory, timeout=expected)
    mark.assert_called_once_with(
        directory, 'Execution process exited (7) without a completion record; see execution.log',
        timeout=expected)


@pytest.mark.parametrize('lock, exited', [
    ('exclusive', False),  # Active process: the GUI's own status read is blocked.
    ('exclusive', True),   # Exited process: its reconciliation status read is blocked.
    ('reserved', True),    # Reads work, but reconciliation cannot start writing.
    ('shared', True),      # Updates work, but reconciliation cannot commit.
])
def test_gui_contention_rolls_back_and_recovers_before_closing(batch, lock, exited):
    before = saved_rows(batch)
    child = process(batch, 0 if exited else None)
    app = SimpleNamespace(
        process=child, batch_directory=batch, interrupt_requested=False, closing=exited,
        status=Mock(), refresh_review=Mock(), destroy=Mock(), after=Mock())
    app.poll_execution = lambda: gui.ExperimentRunnerApp.poll_execution(app)
    blocker = sqlite3.connect(batch / 'manifest.sqlite3', timeout=0)
    try:
        # Acquire the lock synchronously before polling, with no timing race.
        if lock == 'shared':
            blocker.execute('BEGIN')
            blocker.execute('SELECT * FROM batch').fetchall()
        else:
            blocker.execute('BEGIN EXCLUSIVE' if lock == 'exclusive' else 'BEGIN IMMEDIATE')
            blocker.execute("UPDATE batch SET error='uncommitted blocker'")
        started = monotonic()
        app.poll_execution()
        # Generous margin: distinguish a short wait from the old ten seconds.
        assert monotonic() - started < 2
        assert app.process is child
        assert app.batch_directory == batch
        assert 'Could not update batch status:' in app.status.configure.call_args.kwargs['text']
        app.destroy.assert_not_called()
        app.refresh_review.assert_not_called()
        app.after.assert_called_once_with(300, app.poll_execution)
    finally:
        blocker.rollback()
        blocker.close()

    # Includes statuses, timestamps and error fields for both batch and runs:
    # failed reconciliation must not leave even partially committed updates.
    assert saved_rows(batch) == before
    app.poll_execution()
    state = store.batch_status(batch)
    if exited:
        assert state['status'] == 'interrupted'
        assert state['counts'] == dict(running=0, succeeded=1, failed=0, interrupted=1, pending=1)
        assert app.process is None
        app.refresh_review.assert_called_once_with()
        app.destroy.assert_called_once_with()
        # The successful closing callback schedules no further query.
        assert app.after.call_count == 1
    else:
        assert state['status'] == 'running'
        assert app.process is child
        assert app.status.configure.call_args.kwargs['text'].startswith('Running —')
        app.destroy.assert_not_called()
        assert app.after.call_count == 2
    # The completed run survives reconciliation byte-for-byte at the row level.
    assert saved_rows(batch)[1][0] == before[1][0]
