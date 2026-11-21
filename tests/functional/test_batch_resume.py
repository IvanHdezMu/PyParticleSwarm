"""Real solver histories, OS locks and cooperative restart across processes."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from multiprocessing import get_all_start_methods
from pathlib import Path

import pandas as pd
import pytest

from tsp_pso.analysis.analysis import BATCH_COLUMNS, analyze, prepare_batch_groups
from tsp_pso.experiments.batch_store import (
    batch_status,
    create_batch,
    read_batch,
    request_pause,
)
from tsp_pso.experiments.experiment_batch import compile_plan
from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)
from tsp_pso.experiments.experiment_process import BatchProcess

pytestmark = pytest.mark.functional


def wait_for(child, condition):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        state = batch_status(child.directory)
        code = child.poll(sqlite_timeout=.05)
        if condition(state, code):
            return state
        if code is not None:
            pytest.fail(f'Process exited before expected state: {state}')
        time.sleep(.02)
    pytest.fail('Coordinator timeout')


def stop_owned(child):
    if child.process.poll() is None:
        try:
            os.killpg(child.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    child.process.wait(timeout=12)
    assert child.process.poll() is not None



@pytest.mark.parametrize('method', [m for m in ('spawn','forkserver') if m in get_all_start_methods()])
def test_real_pause_resume_keeps_completed_histories(tmp_path, method):
    config = ExperimentConfiguration(datasets=('bays29',), particles=(2,), c1=(2,),
        operators=(3,), permutation_reset=(False,), progress_warmup_multiplier=(0,),
        repetitions=RepetitionSpec(3,37), output_dir=tmp_path)
    directory = create_batch(compile_plan(config))
    # Limit only test worker count; exercise real algorithms and the requested
    # multiprocessing context in an isolated coordinator, without RNG changes.
    code = '''
import sys, multiprocessing as mp
from functools import partial
mp.set_start_method(sys.argv[2])
import tsp_pso.infrastructure.executors.particle_executor as workers
workers.Pool = partial(mp.Pool, processes=1)
from tsp_pso.experiments.batch_executor import execute_batch
execute_batch(sys.argv[1], _process_group=True)
'''
    def launch():
        child = BatchProcess.__new__(BatchProcess)
        child.directory = directory
        with (directory/'execution.log').open('a') as log:
            child.process = subprocess.Popen([sys.executable,'-c',code,str(directory),method],
                cwd=Path(__file__).resolve().parents[2], start_new_session=True,
                stdout=log, stderr=subprocess.STDOUT)
        return child
    child = launch()
    try:
        wait_for(child, lambda s,c: s['counts']['running']==1)
        request_pause(directory)
        state = wait_for(child, lambda s,c: c is not None)
        assert state['status']=='paused' and state['counts']['succeeded']==1
        assert not (directory/'Analysis.xlsx').exists()
    finally:
        stop_owned(child)
    first = read_batch(directory)[2][0]
    original = {p:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (directory/'runs/1').rglob('*') if p.is_file()}
    log_before = (directory/'execution.log').read_bytes()
    child = launch()
    try:
        assert wait_for(child, lambda s,c: c is not None)['status']=='succeeded'
    finally:
        stop_owned(child)
    assert read_batch(directory)[2][0] == first
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in original.items())
    assert (directory/'execution.log').read_bytes().startswith(log_before)
    rows=read_batch(directory)[2]
    assert [json.loads(r['configuration'])['repetition_id'] for r in rows] == [37,38,39]
    expected=analyze({'columns':BATCH_COLUMNS,'output':None},groups=prepare_batch_groups(directory))
    pd.testing.assert_frame_equal(pd.read_excel(directory/'Analysis.xlsx'),expected,
                                  check_dtype=False,rtol=1e-12,atol=1e-12)


def test_second_coordinator_cannot_change_active_batch(tmp_path):
    directory=create_batch(compile_plan(ExperimentConfiguration(datasets=('bays29',),output_dir=tmp_path)))
    code='''
import sys
from tsp_pso.experiments.experiment_process import execution_lock
from tsp_pso.experiments.batch_store import start_batch
with execution_lock(sys.argv[1], retain_owner=True):
    start_batch(sys.argv[1])
    print('ready', flush=True)
    sys.stdin.readline()
'''
    owner=subprocess.Popen([sys.executable,'-c',code,str(directory)],
        cwd=Path(__file__).resolve().parents[2],start_new_session=True,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert owner.stdout.readline().strip()=='ready'
        before=read_batch(directory)[1:]
        second=BatchProcess(directory)
        try:
            wait_for(second,lambda s,c:c is not None)
            assert second.process.returncode != 0
            assert read_batch(directory)[1:]==before
        finally:
            stop_owned(second)
    finally:
        owner.communicate('\n',timeout=5)
