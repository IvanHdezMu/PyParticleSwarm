"""Small offline execution through the new adapter and existing real solver."""
from functools import partial
import json
from multiprocessing import Pool
from pathlib import Path

import pytest

from tsp_pso import base_solver as solver
from tsp_pso.batch_executor import execute_batch
from tsp_pso.batch_store import create_batch, batch_status, connect
from tsp_pso.experiment_batch import DatasetDescriptor, compile_plan
from tsp_pso.experiment_config import ExperimentConfiguration, RepetitionSpec

pytestmark = pytest.mark.functional


def test_offline_batch_writes_real_excel_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(solver, 'Pool', partial(Pool, processes=1))
    dataset = tmp_path / 'tiny.json'
    dataset.write_text(json.dumps({'nodes': [
        {'latitude':40+i*.01,'longitude':-3+i*.01,'price':1.5+i*.01} for i in range(4)]}))
    descriptor = DatasetDescriptor('tiny', str(dataset), 'json', 'offline test', ('tsp','tspwr'))
    configuration = ExperimentConfiguration(
        datasets=('tiny',), problem_modes=('tsp','tspwr'), particles=(2,), c1=(1,),
        operators=(3,), permutation_reset=(False,), progress_warmup_multiplier=(0,),
        repetitions=RepetitionSpec(1,17), output_dir=tmp_path/'results')
    directory = create_batch(compile_plan(configuration,(descriptor,)))
    execute_batch(directory)
    status = batch_status(directory)
    assert status['status'] == 'succeeded', status
    assert status['counts']['succeeded'] == 2
    with connect(directory) as db:
        rows = db.execute('SELECT * FROM runs').fetchall()
    for row in rows:
        output = Path(row['output'])
        assert (output/'run_config.json').is_file()
        assert len(list(output.glob('*.xlsx'))) == 1
        assert json.loads(row['configuration'])['repetition_id'] == 17


@pytest.mark.skipif(__import__('os').name != 'posix', reason='POSIX process-group signal integration')
def test_real_process_interrupt_preserves_finished_run(tmp_path):
    import time
    from tsp_pso.experiment_process import BatchProcess
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
                process.interrupt()
                break
            assert process.poll() is None, state
            time.sleep(.05)
        else:
            pytest.fail('First tiny run did not complete before timeout')
        while process.poll() is None and time.monotonic()<deadline:
            time.sleep(.05)
        assert process.poll() is not None
        state=batch_status(directory)
        assert state['status']=='interrupted'
        assert state['counts']=={'running':0,'succeeded':1,'failed':0,'interrupted':1,'pending':1}
        assert list((directory/'runs/1').rglob('run_config.json'))
    finally:
        process.interrupt()
        cleanup_deadline=time.monotonic()+12
        while process.poll() is None and time.monotonic()<cleanup_deadline:
            time.sleep(.1)
