"""Manifest persistence and adapter tests without expensive solver executions."""
from dataclasses import replace
import json
import pytest

from tsp_pso.experiment_config import ExperimentConfiguration, RepetitionSpec
from tsp_pso.experiment_batch import compile_plan, iterate_runs, load_presets
from tsp_pso.batch_store import create_batch, batch_status, connect, mark_interrupted
from tsp_pso.batch_executor import execute_batch, to_legacy_experiment

pytestmark = pytest.mark.unit


def batch(tmp_path, count=3):
    return create_batch(compile_plan(ExperimentConfiguration(
        datasets=('berlin52',), repetitions=RepetitionSpec(count, 17), output_dir=tmp_path)))


def test_pending_is_implicit_even_for_huge_batch(tmp_path):
    directory = batch(tmp_path, 10**100)
    assert batch_status(directory)['counts']['pending'] == 10**100
    with connect(directory) as db:
        assert db.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 0


def test_success_persists_configuration_and_artifacts(tmp_path):
    directory = batch(tmp_path)
    def run(config, output, descriptor):
        (output / 'result.txt').write_text(str(config.repetition_id))
        return output
    execute_batch(directory, run)
    state = batch_status(directory)
    assert state['status'] == 'succeeded' and state['counts']['succeeded'] == 3
    with connect(directory) as db:
        rows = db.execute('SELECT * FROM runs').fetchall()
    assert [json.loads(r['configuration'])['repetition_id'] for r in rows] == [17,18,19]
    assert all(r['ended_at'] and r['output'] for r in rows)
    with pytest.raises(ValueError, match='resume'):
        execute_batch(directory, run)


@pytest.mark.parametrize('error,status', [(RuntimeError('bad run'),'failed'), (KeyboardInterrupt(),'interrupted')])
def test_failure_and_interrupt_preserve_completed_and_pending(tmp_path, error, status):
    directory = batch(tmp_path)
    def run(config, output, descriptor):
        if config.repetition_id == 18:
            raise error
        (output / 'result.txt').write_text('completed')
        return output
    execute_batch(directory, run)
    state = batch_status(directory)
    assert state['status'] == status
    assert state['counts'] == {'running':0,'succeeded':1,'failed':int(status=='failed'),
                               'interrupted':int(status=='interrupted'),'pending':1}
    assert (directory / 'runs/1/result.txt').read_text() == 'completed'
    assert not (directory / 'runs/3').exists()
    mark_interrupted(directory)
    assert batch_status(directory)['counts']['succeeded'] == 1


def test_adapter_preserves_legacy_names_and_arguments():
    from tsp_pso import runner
    for preset, old in zip(load_presets(), runner.EXPERIMENTS):
        for run in iterate_runs(compile_plan(preset)):
            converted = to_legacy_experiment(run)
            assert converted.k == old.k
            assert converted.refuel == old.refuel
            assert converted.style == old.style
            assert converted.full_tanks == (dict(run.legacy_values)['full_initial_tank'],)
            configuration = next(converted.configurations())
            assert runner.result_filename(converted, configuration) == runner.result_filename(old, configuration)
