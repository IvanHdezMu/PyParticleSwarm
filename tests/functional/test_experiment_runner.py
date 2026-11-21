"""Small offline execution through the new adapter and existing real solver."""
from functools import partial
import json
import os
import signal
from multiprocessing import Pool
from pathlib import Path

import pytest

from tsp_pso.infrastructure.executors import particle_executor as executor_module
from tsp_pso.experiments.batch_executor import execute_batch
from tsp_pso.experiments.batch_store import create_batch, batch_status, connect
from tsp_pso.experiments.experiment_batch import DatasetDescriptor, compile_plan
from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec

pytestmark = pytest.mark.functional


@pytest.mark.parametrize('modes', [('tsp',), ('tspwr',), ('tsp', 'tspwr')])
def test_offline_batch_writes_real_excel_and_manifest(tmp_path, monkeypatch, modes):
    monkeypatch.setattr(executor_module, 'Pool', partial(Pool, processes=1))
    dataset = tmp_path / 'tiny.json'
    dataset.write_text(json.dumps({'nodes': [
        {'latitude':40+i*.01,'longitude':-3+i*.01,'price':1.5+i*.01} for i in range(4)]}))
    descriptor = DatasetDescriptor('tiny', str(dataset), 'json', 'offline test', ('tsp','tspwr'))
    configuration = ExperimentConfiguration(
        datasets=('tiny',), problem_modes=modes, particles=(2,), c1=(1,),
        operators=(3,), permutation_reset=(False,), progress_warmup_multiplier=(0,),
        repetitions=RepetitionSpec(1,17), output_dir=tmp_path/'results')
    directory = create_batch(compile_plan(configuration,(descriptor,)))
    execute_batch(directory)
    status = batch_status(directory)
    assert status['status'] == 'succeeded', status
    assert status['counts']['succeeded'] == len(modes)
    assert (directory / 'Analysis.xlsx').exists() == (len(modes) == 1)
    if len(modes) > 1:
        assert 'analysis failed' in (directory / 'execution.log').read_text()
    with connect(directory) as db:
        rows = db.execute('SELECT * FROM runs').fetchall()
    for row in rows:
        output = Path(row['output'])
        assert (output/'run_config.json').is_file()
        assert len(list(output.glob('*.xlsx'))) == 1
        assert json.loads(row['configuration'])['repetition_id'] == 17


@pytest.mark.skipif(__import__('os').name != 'posix', reason='POSIX process-group signal integration')
def test_external_process_death_preserves_finished_run(tmp_path):
    import time
    from tsp_pso.experiments.experiment_process import BatchProcess
    dataset=tmp_path/'tiny-process.json'
    dataset.write_text(json.dumps({'nodes':[
        {'latitude':40+i*.01,'longitude':-3+i*.01,'price':1.5} for i in range(4)]}))
    descriptor=DatasetDescriptor('tiny',str(dataset),'json','offline',('tsp',))
    configuration=ExperimentConfiguration(
        datasets=('tiny',),particles=(2,),c1=(1,10**8,10**9),operators=(3,),
        permutation_reset=(False,),excel=False,output_dir=tmp_path/'results')
    directory=create_batch(compile_plan(configuration,(descriptor,)))
    process=BatchProcess(directory)
    deadline=time.monotonic()+40
    try:
        while time.monotonic()<deadline:
            state=batch_status(directory)
            if state['counts']['succeeded']==1 and state['counts']['running']==1:
                os.killpg(process.process.pid, signal.SIGKILL)
                break
            assert process.poll() is None, state
            time.sleep(.05)
        else:
            pytest.fail('First tiny run did not complete before timeout')
        while time.monotonic()<deadline:
            if process.poll() is not None and batch_status(directory)['status'] == 'interrupted':
                break
            time.sleep(.05)
        assert process.poll() is not None
        state=batch_status(directory)
        assert state['status']=='interrupted'
        assert state['counts']=={'running':0,'succeeded':1,'failed':0,'interrupted':1,'pending':1}
        assert list((directory/'runs/1').rglob('run_config.json'))
    finally:
        if process.process.poll() is None:
            try:
                os.killpg(process.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.process.wait(timeout=12)
