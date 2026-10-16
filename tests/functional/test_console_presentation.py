"""Presentation preserves sampling frequency, ordering and spawn serialization."""

from contextlib import contextmanager
from multiprocessing import get_context
import os
import pickle

import numpy as np
import pandas as pd
import pytest

import tsp_pso.infrastructure.executors.particle_executor as swarm_module
from tsp_pso.presentation.console_presenter import ConsolePresenter
from tsp_pso.infrastructure.writers.excel_result_writer import ExcelResultWriter

pytestmark = pytest.mark.functional


def legacy_text(step, label, result, member):
    return (f'PARTICLE SWARM: \nCURRENT STEPS: {int(step):d} \n'
            f'BEST {label}: {result:f} \nBEST MEMBER: {member} \n\n')


@pytest.mark.parametrize('refuel', [False, True])
@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('excel', [False, True])
@pytest.mark.parametrize('samples', [False, True])
def test_presenter_with_real_spawn(monkeypatch, make_solver, tmp_path, capsys,
                                   refuel, verbose, excel, samples):
    solver = make_solver(refuel_mode=refuel, c1=6,
                         progressWarmupMultiplier=1 if samples else 100)
    cls = type(solver)
    destination = tmp_path / 'result.xlsx'
    events = []
    measures = []
    formatted = []
    parent_pid = os.getpid()

    @contextmanager
    def tracked_pool():
        with get_context('spawn').Pool(processes=1, initializer=np.random.seed,
                                       initargs=(7,)) as pool:
            yield pool
        events.append(('pool closed', solver.cur_steps))

    monkeypatch.setattr(swarm_module, 'Pool', tracked_pool)
    original_measure = cls._dataToSave
    original_best = cls._best
    original_global = cls._global_best

    def measure(instance):
        value = original_measure(instance)
        measures.append(value)
        events.append(('measure', instance.cur_steps))
        return value

    def best(instance):
        original_best(instance)
        events.append(('best', instance.cur_steps))

    def global_best(instance):
        original_global(instance)
        events.append(('global best', instance.cur_steps))

    monkeypatch.setattr(cls, '_dataToSave', measure)
    monkeypatch.setattr(cls, '_best', best)
    monkeypatch.setattr(cls, '_global_best', global_best)

    class ParentPresenter(ConsolePresenter):
        def __reduce__(self):
            raise AssertionError('Presenter must not be serialized')

        def format_result(self, step, label, result, member):
            assert os.getpid() == parent_pid
            assert isinstance(member, str)
            assert np.isscalar(step)
            assert np.isscalar(result)
            assert isinstance(label, str)
            record = (step, label, result, member)
            formatted.append(record)
            events.append(('format', step))
            return super().format_result(*record)

        def present_result(self, text):
            assert os.getpid() == parent_pid
            assert isinstance(text, str)
            events.append(('present', solver.cur_steps))
            super().present_result(text)

        def present_completion(self):
            events.append(('completion', solver.cur_steps))
            super().present_completion()

    class RecordingWriter:
        def __reduce__(self):
            raise AssertionError('Writer must not be serialized')

        def write(self, history, file_path):
            assert events[-1] == ('pool closed', solver.cur_steps)
            assert ('completion', solver.cur_steps) not in events
            events.append(('write', solver.cur_steps))
            ExcelResultWriter().write(history, file_path)

    presenter = ParentPresenter()
    writer = RecordingWriter()
    monkeypatch.setattr(cls, 'console_presenter', presenter)
    monkeypatch.setattr(cls, 'result_writer', writer)
    for obj in (solver, solver._compute_position):
        restored = pickle.loads(pickle.dumps(obj))
        state = vars(restored.__self__ if hasattr(restored, '__self__') else restored)
        assert 'console_presenter' not in state
        assert 'result_writer' not in state

    result = solver.run(verbose=verbose, excel=excel, file_path=destination,
                        optType=3, permutReset=False, k=2)
    events.append(('returned', solver.cur_steps))
    output = capsys.readouterr().out
    sample_steps = [5, 13, 25] if samples else []
    expected = [('global best', 1)]
    expected_measure_steps = []
    for step in [5, 13, 25]:
        expected.extend([('best', step), ('global best', step)])
        if step in sample_steps:
            if verbose:
                expected.extend([('measure', step), ('format', step), ('present', step)])
                expected_measure_steps.append(step)
            if excel:
                expected.append(('measure', step))
                expected_measure_steps.append(step)
    expected.append(('pool closed', 25))
    if excel:
        expected.append(('write', 25))
    expected.extend([('completion', 25), ('measure', 25), ('format', 25),
                     ('present', 25), ('returned', 25)])
    expected_measure_steps.append(25)
    assert events == expected
    assert [step for step, _ in measures] == expected_measure_steps
    assert len(formatted) == (len(sample_steps) if verbose else 0) + 1
    assert output == (''.join(legacy_text(*record) + '\n' for record in formatted[:-1])
                      + 'TERMINATING - REACHED MAXIMUM STEPS\n'
                      + legacy_text(*formatted[-1]) + '\n')
    assert formatted[-1][1] == ('REFUEL COST' if refuel else 'DISTANCE')
    if excel:
        frame = pd.read_excel(destination)
        assert frame['Step'].tolist() == sample_steps
        assert list(frame.columns) == ['Step', 'Result']
    else:
        assert not destination.exists()
    assert all(value is not presenter and value is not writer for value in vars(solver).values())
    assert result[0] is not None
    np.testing.assert_array_equal(result[0], solver.global_best[0])
    assert result[1] == solver._objective(result[0])

    # Standalone representations must each calculate the measure exactly once.
    count = len(measures)
    expected_text = legacy_text(*formatted[-1])
    assert str(solver) == expected_text
    assert repr(solver) == expected_text
    assert len(measures) == count + 2
    assert capsys.readouterr().out == ''


def test_completion_is_printed_before_final_measure_failure(monkeypatch, solver, capsys):
    @contextmanager
    def empty_pool():
        yield None

    solver.max_steps = 0
    monkeypatch.setattr(swarm_module, 'Pool', empty_pool)
    failure = ValueError('cannot calculate final measure')

    def measure(instance):
        raise failure

    monkeypatch.setattr(type(solver), '_dataToSave', measure)
    with pytest.raises(ValueError) as caught:
        solver.run(verbose=False)
    assert caught.value is failure
    assert capsys.readouterr().out == 'TERMINATING - REACHED MAXIMUM STEPS\n'
