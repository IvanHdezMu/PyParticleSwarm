"""Batch launch errors and retry behavior without a Tk window or filesystem I/O."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import sqlite3

import pytest

from tsp_pso.presentation import experiment_gui as gui

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    plan = SimpleNamespace(configuration=SimpleNamespace(output_dir=Path('/results')))
    window = SimpleNamespace(
        process=None, batch_directory=None, status=Mock(), run_button=Mock(),
        validated_review=Mock(return_value=(plan, 3, ('A warning',))))
    window.launch = lambda: gui.ExperimentRunnerApp.launch(window)
    return window


@pytest.fixture
def services(monkeypatch):
    services = SimpleNamespace(
        confirm=Mock(return_value=True), create=Mock(return_value=Path('/batch')),
        start=Mock(), finish=Mock())
    monkeypatch.setattr(gui.messagebox, 'askyesno', services.confirm)
    monkeypatch.setattr(gui, 'create_batch', services.create)
    monkeypatch.setattr(gui, 'BatchProcess', services.start)
    monkeypatch.setattr(gui, 'finish_batch', services.finish)
    return services


def test_launch_success(app, services):
    app.launch()
    services.confirm.assert_called_once_with(
        'Run batch', 'Run exactly 3 executions?\n\nOutput: /results\n\nA warning', parent=app)
    services.create.assert_called_once_with(app.validated_review.return_value[0])
    services.start.assert_called_once_with(Path('/batch'))
    assert app.batch_directory == Path('/batch')
    assert app.process is services.start.return_value
    app.run_button.configure.assert_called_once_with(state='disabled')
    app.status.configure.assert_called_once_with(text='Batch starting…\n/batch')
    services.finish.assert_not_called()


def test_cancel_does_not_create_batch(app, services):
    services.confirm.return_value = False
    app.launch()
    services.create.assert_not_called()
    services.start.assert_not_called()
    services.finish.assert_not_called()
    assert app.process is None
    assert app.batch_directory is None
    app.run_button.configure.assert_not_called()


@pytest.mark.parametrize('error', [OSError('disk full'), sqlite3.OperationalError('locked')])
def test_batch_creation_failure_is_visible_and_retryable(app, services, error):
    services.create.side_effect = [error, Path('/retry')]
    app.launch()
    app.status.configure.assert_called_once_with(text=f'Could not launch: {error}')
    assert app.process is None
    app.run_button.configure.assert_not_called()
    services.start.assert_not_called()
    services.finish.assert_not_called()
    app.launch()
    assert app.batch_directory == Path('/retry')
    assert app.process is services.start.return_value
    services.start.assert_called_once_with(Path('/retry'))
    app.run_button.configure.assert_called_once_with(state='disabled')


def test_process_start_failure_is_recorded_and_retryable(app, services):
    process = Mock()
    services.start.side_effect = [OSError('cannot start child'), process]
    app.launch()
    services.finish.assert_called_once_with(Path('/batch'), 'failed', 'cannot start child')
    app.status.configure.assert_called_once_with(text='Could not launch: cannot start child')
    assert app.process is None
    assert app.batch_directory == Path('/batch')
    app.run_button.configure.assert_not_called()
    services.create.return_value = Path('/retry')
    app.launch()
    assert app.process is process
    assert app.batch_directory == Path('/retry')
    assert services.finish.call_count == 1


@pytest.mark.parametrize('secondary', [OSError('disk full'), sqlite3.OperationalError('locked')])
def test_recording_failure_preserves_both_errors_and_allows_retry(app, services, secondary):
    process = Mock()
    services.start.side_effect = [OSError('cannot start child'), process]
    services.finish.side_effect = secondary
    app.launch()
    app.status.configure.assert_called_once_with(text=(
        'Could not launch: cannot start child\n'
        f'Could not record batch failure: {secondary}'))
    assert app.process is None
    assert app.batch_directory == Path('/batch')
    app.run_button.configure.assert_not_called()
    services.create.return_value = Path('/retry')
    app.launch()
    assert app.process is process
    assert app.batch_directory == Path('/retry')
    app.run_button.configure.assert_called_once_with(state='disabled')


def test_active_process_prevents_second_launch(app, services):
    app.process = Mock()
    app.launch()
    app.validated_review.assert_not_called()
    services.confirm.assert_not_called()
    services.create.assert_not_called()


def test_invalid_configuration_still_reports_validation_error(app, services):
    app.validated_review.side_effect = ValueError('invalid configuration')
    app.launch()
    app.status.configure.assert_called_once_with(text='Could not launch: invalid configuration')
    services.confirm.assert_not_called()
    services.create.assert_not_called()


@pytest.mark.parametrize('operation', ['create', 'start', 'finish'])
def test_programming_errors_are_not_hidden(app, services, operation):
    if operation == 'finish':
        services.start.side_effect = OSError('cannot start child')
    getattr(services, operation).side_effect = TypeError('bug')
    with pytest.raises(TypeError, match='bug'):
        app.launch()
