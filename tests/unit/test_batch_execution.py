"""Manifest persistence and adapter tests without expensive solver executions."""
import json

import pytest
from conftest import concrete_tuple

from tsp_pso.experiments.batch_executor import execute_batch
from tsp_pso.experiments.batch_store import (
    batch_status,
    connect,
    create_batch,
    mark_interrupted,
)
from tsp_pso.experiments.experiment_batch import (
    compile_plan,
    iterate_runs,
    load_presets,
)
from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)
from tsp_pso.experiments.result_naming import result_filename
from tsp_pso.infrastructure.experiment_options import load_preset_options

pytestmark = pytest.mark.unit


def batch(tmp_path, count=3):
    return create_batch(compile_plan(ExperimentConfiguration(
        datasets=('berlin52',), repetitions=RepetitionSpec(count, 17), output_dir=tmp_path)))


def test_huge_batch_rejected_before_materialization(tmp_path):
    with pytest.raises(ValueError, match='at most 10,000'):
        batch(tmp_path, 10**100)
    assert not list(tmp_path.iterdir())


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


def test_concrete_runs_preserve_historical_names_and_values():
    options = load_preset_options()
    for preset, entry in zip(load_presets(), options['experiments']):
        saved = {**options['defaults'], **entry}
        for run in iterate_runs(compile_plan(preset)):
            assert run.legacy_label == saved['label']
            assert dict(run.legacy_values)['k'] == saved['k']
            assert (run.problem_mode == 'tspwr') == saved['refuel']
            n, c1, opt, minimum, maximum, ring, full, number = concrete_tuple(run)
            suffix = {
                'fuel': f'{ring}_{full}_{number}', 'bays': str(number),
                'berlin_grid': f"{saved['k']}_{number}_{minimum}_{maximum}",
                'standard': f"{saved['k']}_{minimum}_{maximum}_{number}",
            }[saved['style']]
            assert result_filename(run.dataset, run.legacy_style, saved['k'], concrete_tuple(run)) == (
                f"{saved['dataset']}_True_{n}_{c1}_{opt}_{suffix}.xlsx")
