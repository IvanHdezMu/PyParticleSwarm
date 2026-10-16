"""Writer injection stays in the parent, outside serialized worker state."""

from contextlib import contextmanager
from functools import partial
from multiprocessing import get_context
import os
import pickle

import numpy as np
import pandas as pd
import pytest

import tsp_pso.infrastructure.executors.particle_executor as swarm_module
from tsp_pso.infrastructure.writers.excel_result_writer import ExcelResultWriter

pytestmark = pytest.mark.functional


@pytest.mark.parametrize('refuel', [False, True])
@pytest.mark.parametrize('excel', [False, True])
@pytest.mark.parametrize('samples', [False, True])
def test_external_writer_with_spawn(monkeypatch, make_solver, tmp_path, capsys,
                                    refuel, excel, samples):
    solver = make_solver(refuel_mode=refuel, c1=6 if samples else 2)
    destination = tmp_path / 'results.xlsx'
    parent_pid = os.getpid()
    events = []
    history_written = []

    @contextmanager
    def tracked_pool():
        with get_context('spawn').Pool(processes=1, initializer=np.random.seed,
                                       initargs=(7,)) as pool:
            yield pool
        events.append('pool closed')

    monkeypatch.setattr(swarm_module, 'Pool', tracked_pool)

    class ParentOnlyWriter:
        def __reduce__(self):
            raise AssertionError('Writer must never be serialized')

        def write(self, history, file_path):
            assert os.getpid() == parent_pid
            assert events == ['pool closed']
            assert solver.cur_steps > solver.max_steps
            assert solver.f_global_best[0] == solver._objective(solver.global_best[0])
            assert 'TERMINATING' not in capsys.readouterr().out
            assert file_path == destination
            history_written.extend(history)
            events.append('write')
            ExcelResultWriter().write(history, file_path)

    writer = ParentOnlyWriter()
    monkeypatch.setattr(type(solver), 'result_writer', writer)
    assert 'result_writer' not in vars(solver)
    restored = pickle.loads(pickle.dumps(solver))
    assert 'result_writer' not in vars(restored)
    # A bound method is the callable actually passed to Pool.map.
    restored_method = pickle.loads(pickle.dumps(solver._compute_position))
    assert 'result_writer' not in vars(restored_method.__self__)

    result = solver.run(verbose=False, excel=excel, file_path=destination,
                        optType=3, permutReset=False, k=2)
    events.append('returned')
    expected_events = ['pool closed', 'write', 'returned'] if excel else ['pool closed', 'returned']
    assert events == expected_events
    assert 'result_writer' not in vars(solver)
    assert all(value is not writer for value in vars(solver).values())
    assert result[1] == solver._objective(result[0])
    output = capsys.readouterr().out
    assert output == 'TERMINATING - REACHED MAXIMUM STEPS\n' + str(solver) + '\n'

    if excel:
        frame = pd.read_excel(destination)
        assert list(frame.columns) == ['Step', 'Result']
        expected_steps = [25] if samples else []
        assert frame['Step'].tolist() == expected_steps
        assert [row[0] for row in history_written] == expected_steps
        if samples:
            np.testing.assert_allclose(frame['Result'], [row[1] for row in history_written])
            assert history_written == [solver._dataToSave()]
    else:
        assert history_written == []
        assert not destination.exists()


def test_writer_failure_prevents_final_print_and_return(monkeypatch, solver, tmp_path, capsys):
    monkeypatch.setattr(swarm_module, 'Pool', partial(get_context('spawn').Pool, processes=1))
    failure = OSError('write failed')
    calls = []

    class FailingWriter:
        def write(self, history, file_path):
            assert solver.cur_steps > solver.max_steps
            calls.append(history)
            raise failure

    monkeypatch.setattr(type(solver), 'result_writer', FailingWriter())
    with pytest.raises(OSError) as caught:
        solver.run(verbose=False, excel=True, file_path=tmp_path / 'results.xlsx',
                   optType=3, permutReset=False)
    assert caught.value is failure
    assert len(calls) == 1
    assert calls[0] == []
    assert capsys.readouterr().out == ''


def test_missing_path_is_rejected_before_clear_or_writer(monkeypatch, solver):
    class UnexpectedWriter:
        def write(self, history, file_path):
            pytest.fail('writer must not be called')

    def unexpected_clear(*args):
        pytest.fail('_clear must not be called')

    monkeypatch.setattr(type(solver), 'result_writer', UnexpectedWriter())
    monkeypatch.setattr(solver, '_clear', unexpected_clear)
    with pytest.raises(ValueError, match='file_path is required when excel=True'):
        solver.run(excel=True)
    assert solver.pos is None
