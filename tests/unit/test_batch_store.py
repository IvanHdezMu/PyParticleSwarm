"""Consistent manifest reads and transaction cleanup."""
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace

import pytest

from tsp_pso.experiments import batch_store
from tsp_pso.experiments.experiment_batch import compile_plan, iterate_runs
from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec

pytestmark = pytest.mark.unit


@pytest.fixture
def batch(tmp_path):
    plan = compile_plan(ExperimentConfiguration(
        datasets=('berlin52',), repetitions=RepetitionSpec(3, 17), output_dir=tmp_path))
    return batch_store.create_batch(plan), tuple(iterate_runs(plan))


@pytest.mark.parametrize('status', ['pending', 'running', 'succeeded', 'failed', 'interrupted'])
def test_status_contract_and_implicit_pending(batch, status):
    directory, runs = batch
    expected = dict(running=0, succeeded=0, failed=0, interrupted=0, pending=3)
    if status != 'pending':
        batch_store.start_batch(directory)
        batch_store.start_run(directory, 1, runs[0])
        batch_store.finish_run(directory, 1, 'succeeded', output=directory / 'runs/1')
        batch_store.start_run(directory, 2, runs[1])
        expected.update(succeeded=1, pending=1)
        if status == 'running':
            expected['running'] = 1
        elif status == 'interrupted':
            batch_store.mark_interrupted(directory)
            expected['interrupted'] = 1
        else:
            batch_store.finish_run(directory, 2, status)
            expected[status] += 1
            if status == 'succeeded':
                batch_store.start_run(directory, 3, runs[2])
                batch_store.finish_run(directory, 3, 'succeeded')
                expected.update(succeeded=3, pending=0)
            batch_store.finish_batch(directory, status)
    state = batch_store.batch_status(directory)
    assert set(state) == {'id', 'total', 'status', 'created_at', 'started_at',
                          'ended_at', 'error', 'counts', 'current', 'ordinal'}
    assert state['status'] == status
    assert type(state['total']) is int and state['total'] == 3
    assert state['counts'] == expected
    assert all(type(value) is int for value in state['counts'].values())
    assert state['ordinal'] == (2 if status == 'running' else None)
    assert state['current'] == (runs[1].to_dict() if status == 'running' else None)


@pytest.mark.parametrize('journal', ['delete', 'wal'])
def test_status_snapshot_during_concurrent_update(batch, monkeypatch, journal):
    directory, runs = batch
    batch_store.start_batch(directory)
    batch_store.start_run(directory, 1, runs[0])
    before = batch_store.batch_status(directory)
    original_connect = batch_store.connect
    writer = sqlite3.connect(directory / 'manifest.sqlite3', timeout=0)
    try:
        # WAL is confined to this test database: it permits a commit while the
        # reader holds its snapshot. DELETE exercises production's default mode.
        assert writer.execute(f'PRAGMA journal_mode={journal}').fetchone()[0] == journal
        interleaved = []

        def update():
            writer.execute("UPDATE runs SET status='succeeded' WHERE ordinal='1'")

        @contextmanager
        def interleave(path):
            with original_connect(path) as reader:
                def execute(sql):
                    if 'LIMIT 1' in sql:
                        update()
                        if journal == 'wal':
                            writer.commit()
                        else:
                            with pytest.raises(sqlite3.OperationalError, match='locked'):
                                writer.commit()
                            writer.rollback()
                        interleaved.append(True)
                    return reader.execute(sql)
                yield SimpleNamespace(execute=execute)

        with monkeypatch.context() as patch:
            patch.setattr(batch_store, 'connect', interleave)
            state = batch_store.batch_status(directory)
        assert interleaved == [True]
        assert state == before
        if journal == 'delete':
            update()
            writer.commit()  # The completed read no longer blocks this commit.
        after = batch_store.batch_status(directory)
        assert after['counts'] == dict(running=0, succeeded=1, failed=0,
                                       interrupted=0, pending=2)
        assert after['current'] is None and after['ordinal'] is None
        assert writer.execute('PRAGMA journal_mode').fetchone()[0] == journal
    finally:
        writer.close()


@pytest.mark.parametrize('failure', [None, 'query', 'decode'])
def test_status_closes_transaction_and_connection(batch, monkeypatch, failure):
    directory, runs = batch
    database = directory / 'manifest.sqlite3'
    writer = sqlite3.connect(database, timeout=0)
    try:
        if failure == 'query':
            writer.execute('DROP TABLE runs')
            writer.commit()
        elif failure == 'decode':
            batch_store.start_batch(directory)
            batch_store.start_run(directory, 1, runs[0])
            writer.execute("UPDATE runs SET configuration='invalid JSON'")
            writer.commit()
        reader = sqlite3.connect(database)
        statements = []
        reader.set_trace_callback(statements.append)
        with monkeypatch.context() as patch:
            patch.setattr(batch_store.sqlite3, 'connect', lambda *args, **kwargs: reader)
            if failure:
                error = sqlite3.OperationalError if failure == 'query' else ValueError
                with pytest.raises(error):
                    batch_store.batch_status(directory)
            else:
                batch_store.batch_status(directory)
        assert statements[0] == 'BEGIN'
        assert statements[-1] == ('ROLLBACK' if failure == 'query' else 'COMMIT')
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            reader.execute('SELECT 1')
        writer.execute('BEGIN EXCLUSIVE')
        writer.execute("UPDATE batch SET error='reader released'")
        writer.commit()
    finally:
        writer.close()
