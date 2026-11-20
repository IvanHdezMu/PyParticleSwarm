"""Postprocessing cannot change successful scientific execution or retry runs."""
import pytest

from tsp_pso.analysis import analysis
from tsp_pso.experiments.batch_executor import execute_batch
from tsp_pso.experiments.batch_store import batch_status


def test_automatic_summary_after_success(batch_artifacts, monkeypatch):
    directory, write = batch_artifacts(completed=False, particles=(2, 4))
    original = analysis.analyze_batch
    calls = []

    def checked(path):
        assert batch_status(path)['status'] == 'succeeded'
        calls.append(path)
        return original(path)

    monkeypatch.setattr(analysis, 'analyze_batch', checked)
    assert execute_batch(directory, write) == directory
    assert calls == [directory]
    assert (directory / 'Analysis.xlsx').is_file()


@pytest.mark.parametrize('error', [ValueError('bad history'), KeyboardInterrupt()])
def test_analysis_failure_keeps_success_and_does_not_repeat(batch_artifacts, monkeypatch, error):
    directory, write = batch_artifacts(completed=False)
    executed = []

    def run(*args):
        executed.append(args[0].repetition_id)
        return write(*args)

    def fail(path):
        raise error

    monkeypatch.setattr(analysis, 'analyze_batch', fail)
    execute_batch(directory, run)
    assert executed == [17, 18]
    state = batch_status(directory)
    assert state['status'] == 'succeeded'
    assert state['counts']['succeeded'] == 2
    assert type(error).__name__ in (directory / 'execution.log').read_text()
    assert not (directory / 'Analysis.xlsx').exists()


@pytest.mark.parametrize('error, status', [(ValueError('run failed'), 'failed'),
                                           (KeyboardInterrupt(), 'interrupted')])
def test_unsuccessful_execution_never_analyzes(batch_artifacts, monkeypatch, error, status):
    directory, _ = batch_artifacts(completed=False)
    calls = []
    monkeypatch.setattr(analysis, 'analyze_batch', lambda path: calls.append(path))

    def fail(*args):
        raise error

    execute_batch(directory, fail)
    assert batch_status(directory)['status'] == status
    assert calls == []


@pytest.mark.parametrize('options, explanation', [({'excel': False}, 'excel=False'),
                                                 ({'history': lambda run: []}, 'valid results')])
def test_unusable_histories_logged_separately(batch_artifacts, options, explanation):
    directory, write = batch_artifacts(completed=False, **options)
    execute_batch(directory, write)
    assert batch_status(directory)['status'] == 'succeeded'
    assert explanation in (directory / 'execution.log').read_text()
    assert not (directory / 'Analysis.xlsx').exists()
