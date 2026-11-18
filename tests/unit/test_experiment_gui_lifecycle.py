"""Observable GUI lifecycle behavior without creating a Tk window."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import sqlite3

import pytest

from tsp_pso.presentation import experiment_gui as gui

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    window = SimpleNamespace(
        process=Mock(), batch_directory=Path('/batch'), interrupt_requested=False,
        closing=False, status=Mock(), refresh_review=Mock(), after=Mock(),
        destroy=Mock())
    window.process.poll.return_value = None
    window.poll_execution = lambda: gui.ExperimentRunnerApp.poll_execution(window)
    return window


@pytest.fixture
def status(monkeypatch):
    read = Mock(return_value={
        'status': 'running', 'counts': {'succeeded': 1, 'failed': 0, 'interrupted': 0},
        'total': 3, 'current': {'dataset': 'tiny', 'operator': 3, 'k': 10},
        'ordinal': 2, 'error': None})
    monkeypatch.setattr(gui, 'batch_status', read)
    return read


def test_normal_poll(app, status):
    app.poll_execution()
    app.process.poll.assert_called_once_with(sqlite_timeout=0.05)
    status.assert_called_once_with(app.batch_directory, timeout=0.05)
    assert app.status.configure.call_args.kwargs['text'] == (
        'Running — 1 / 3 finished\nRun 2: tiny · operator 3 · k 10\n/batch')
    app.after.assert_called_once_with(300, app.poll_execution)
    app.destroy.assert_not_called()
    app.refresh_review.assert_not_called()


def test_transient_sqlite_error_recovers(app, status):
    process = app.process
    status.side_effect = [sqlite3.OperationalError('locked'), status.return_value]
    app.poll_execution()
    assert 'Could not update batch status: locked' in app.status.configure.call_args.kwargs['text']
    assert app.process is process
    app.poll_execution()
    assert app.status.configure.call_args.kwargs['text'].startswith('Running —')
    assert app.after.call_count == 2


def test_persistent_error_retains_execution_and_replaces_diagnostic(app, status):
    process = app.process
    status.side_effect = sqlite3.OperationalError('locked')
    for _ in range(3):
        app.poll_execution()
    assert app.process is process
    assert app.batch_directory == Path('/batch')
    assert app.after.call_count == 3
    texts = [call.kwargs['text'] for call in app.status.configure.call_args_list]
    assert texts == ['Could not update batch status: locked\n/batch'] * 3
    app.destroy.assert_not_called()
    app.refresh_review.assert_not_called()


@pytest.mark.parametrize('error', [OSError('process unavailable'), sqlite3.OperationalError('locked')])
def test_process_poll_error(app, status, error):
    process = app.process
    process.poll.side_effect = error
    app.poll_execution()
    assert str(error) in app.status.configure.call_args.kwargs['text']
    assert app.process is process
    status.assert_not_called()
    app.after.assert_called_once_with(300, app.poll_execution)


def test_close_during_status_failure_then_process_finishes(app, status):
    process = app.process
    app.closing = True
    status.side_effect = [sqlite3.OperationalError('locked'), status.return_value]
    process.poll.side_effect = [None, 0]
    app.poll_execution()
    process.interrupt.assert_called_once_with()
    app.destroy.assert_not_called()
    assert app.process is process
    app.after.assert_called_once_with(300, app.poll_execution)
    app.poll_execution()
    assert process.interrupt.call_count == 2
    app.destroy.assert_called_once_with()
    assert app.process is None
    # The closing poll must not schedule any work after destruction.
    assert app.after.call_count == 1


def test_finished_process_kept_until_status_can_be_read(app, status):
    process = app.process
    process.poll.return_value = 0
    status.side_effect = [sqlite3.OperationalError('locked'), status.return_value]
    app.poll_execution()
    assert app.process is process
    app.poll_execution()
    assert app.process is None
    app.refresh_review.assert_called_once_with()
    assert app.after.call_count == 2


def test_interrupt_failure_is_retried(app, status):
    app.interrupt_requested = True
    app.process.interrupt.side_effect = [OSError('signal failed'), None]
    app.poll_execution()
    assert app.interrupt_requested
    app.process.poll.assert_not_called()
    app.poll_execution()
    assert not app.interrupt_requested
    assert app.process.interrupt.call_count == 2
    assert app.after.call_count == 2


def test_idle_interrupt_destroys_without_scheduling(app, status):
    app.process = None
    app.interrupt_requested = True
    app.poll_execution()
    app.destroy.assert_called_once_with()
    app.after.assert_not_called()
    status.assert_not_called()


def test_programming_error_is_not_hidden(app, status):
    app.process.poll.side_effect = TypeError('bug')
    with pytest.raises(TypeError, match='bug'):
        app.poll_execution()
