"""Asynchronous preparation and saved-batch launch, without Tk."""
import sqlite3
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tsp_pso.presentation import experiment_gui as gui


@pytest.fixture
def app():
    plan = SimpleNamespace(configuration=SimpleNamespace(output_dir=Path('/results')))
    window = SimpleNamespace(process=None, preparing=None, selected_batch=None, closing=False,
        batch_directory=None, worker=Mock(), status=Mock(), run_button=Mock(), back_button=Mock(),
        set_form_enabled=Mock(), after=Mock(), refresh_review=Mock(), update_run_button=Mock(),
        destroy=Mock(), validated_review=Mock(return_value=(plan,3,())))
    for name in ('launch','finish_preparation','start_saved_batch'):
        setattr(window,name,lambda n=name: getattr(gui.ExperimentRunnerApp,n)(window))
    return window


@pytest.fixture
def services(monkeypatch):
    confirm=Mock(return_value=True)
    start=Mock()
    read=Mock(return_value={'status':'pending'})
    monkeypatch.setattr(gui.messagebox,'askyesno',confirm)
    monkeypatch.setattr(gui,'BatchProcess',start)
    monkeypatch.setattr(gui,'batch_status',read)
    return confirm,start,read


def test_preparation_is_off_thread_and_launch_waits(app, services):
    _, start, _ = services
    future=Future(); app.worker.submit.return_value=future
    app.launch()
    app.worker.submit.assert_called_once_with(gui.create_batch,app.validated_review.return_value[0])
    start.assert_not_called()
    app.finish_preparation()
    start.assert_not_called()
    future.set_result(Path('/batch'))
    app.finish_preparation()
    start.assert_called_once_with(Path('/batch'))
    assert app.process is start.return_value


def test_cancel_and_preparing_prevent_duplicate_launch(app, services):
    confirm,start,_=services
    confirm.return_value=False
    app.launch()
    app.worker.submit.assert_not_called()
    app.preparing=Future()
    confirm.reset_mock()
    app.launch()
    confirm.assert_not_called()
    start.assert_not_called()


@pytest.mark.parametrize('error',[OSError('disk full'),sqlite3.OperationalError('locked')])
def test_preparation_failure_is_visible_and_retryable(app, services, error):
    future=Future();future.set_exception(error);app.preparing=future
    app.finish_preparation()
    assert app.preparing is None and app.process is None
    assert str(error) in app.status.configure.call_args.kwargs['text']
    app.set_form_enabled.assert_called_once_with(True)


def test_start_failure_preserves_saved_queue(app, services):
    _,start,_=services
    start.side_effect=OSError('cannot launch')
    app.selected_batch={'status':'pending'};app.batch_directory=Path('/saved')
    app.launch()
    assert app.process is None and app.batch_directory==Path('/saved')
    app.worker.submit.assert_not_called()
    assert 'cannot launch' in app.status.configure.call_args.kwargs['text']


def test_saved_resume_does_not_create_another_batch(app, services):
    _,start,_=services
    app.selected_batch={'status':'paused'};app.batch_directory=Path('/saved')
    app.launch()
    app.worker.submit.assert_not_called()
    app.validated_review.assert_not_called()
    start.assert_called_once_with(Path('/saved'))


def test_active_button_requests_pause_without_signal(app, services):
    app.process=Mock()
    app.launch()
    app.process.pause.assert_called_once_with()
    app.worker.submit.assert_not_called()
    assert app.run_button.configure.call_args.kwargs['text']=='Pausing…'


def test_close_during_preparation_keeps_pending_queue(app, services):
    _,start,_=services
    future=Future();future.set_result(Path('/batch'));app.preparing=future;app.closing=True
    app.finish_preparation()
    start.assert_not_called()
    app.destroy.assert_called_once_with()


@pytest.mark.parametrize('status',['succeeded','failed'])
def test_read_only_batches_cannot_launch(app, services, status):
    _,start,read=services
    app.selected_batch={};app.batch_directory=Path('/batch')
    read.return_value={'status':status}
    app.launch()
    start.assert_not_called()
    assert 'Could not launch' in app.status.configure.call_args.kwargs['text']
