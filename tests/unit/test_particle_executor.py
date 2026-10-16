"""Pool delegation and solver ownership of the executor lifetime."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from tsp_pso.infrastructure.executors import particle_executor as executor_module
from tsp_pso.infrastructure.executors.particle_executor import ParticleExecutor

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('failure', [None, RuntimeError('worker failed'), KeyboardInterrupt()])
def test_pool_context_and_map_are_delegated(monkeypatch, failure):
    context = MagicMock()
    pool = context.__enter__.return_value
    context.__exit__.return_value = False
    constructor = MagicMock(return_value=context)
    monkeypatch.setattr(executor_module, 'Pool', constructor)
    function = object()
    iterable = iter([object()])
    result = object()
    pool.map.return_value = result
    pool.map.side_effect = failure

    def execute():
        with ParticleExecutor() as executor:
            assert executor.map(function, iterable) is result

    if failure is None:
        execute()
        context.__exit__.assert_called_once_with(None, None, None)
    else:
        with pytest.raises(type(failure)) as caught:
            execute()
        assert caught.value is failure
        args = context.__exit__.call_args.args
        assert args[0] is type(failure)
        assert args[1] is failure
        assert args[2] is not None
    constructor.assert_called_once_with()
    context.__enter__.assert_called_once_with()
    pool.map.assert_called_once_with(function, iterable)
    assert next(iterable) is not None  # The wrapper has not consumed it.


@pytest.mark.parametrize('refuel', [False, True])
@pytest.mark.parametrize('iterations', [False, True])
def test_one_pool_after_clear_per_run(monkeypatch, make_solver, refuel, iterations):
    solver = make_solver(refuel_mode=refuel, c1=6 if iterations else 0)
    events = []
    pools = []
    clear = solver._clear

    def tracked_clear(*args):
        clear(*args)
        events.append('clear')

    # Patch the class, so the solver's serialized instance remains unchanged.
    monkeypatch.setattr(type(solver), '_clear', lambda self, *args: tracked_clear(*args))

    class Pool:
        def __init__(self):
            assert events[-1] == 'clear'
            events.append('create')
            pools.append(self)
            self.calls = 0

        def __enter__(self):
            events.append('enter')
            return self

        def map(self, function, iterable):
            assert function.__self__ is solver
            assert function.__func__ is type(solver)._compute_position
            assert isinstance(iterable, zip)
            args = list(iterable)
            assert len(args) == solver.swarm_size
            for i, (x, vel, n_iter, fx) in enumerate(args):
                np.testing.assert_array_equal(x, solver.pos[i])
                np.testing.assert_array_equal(vel, solver.vel[i])
                assert n_iter == solver.nIter[i]
                assert fx == solver.fx[i]
            self.calls += 1
            return [(x, n_iter, fx, vel) for x, vel, n_iter, fx in args]

        def __exit__(self, *exc):
            assert exc == (None, None, None)
            events.append('exit')

    monkeypatch.setattr(executor_module, 'Pool', Pool)
    for _ in range(2):
        solver.run(verbose=False)
    assert events == ['clear', 'create', 'enter', 'exit'] * 2
    assert len(pools) == 2
    assert [pool.calls for pool in pools] == ([3, 3] if iterations else [0, 0])


def test_parent_interrupt_closes_pool_without_output(monkeypatch, solver, tmp_path, capsys):
    failure = KeyboardInterrupt()
    pool = MagicMock()
    pool.__enter__.return_value = pool
    pool.__exit__.return_value = False
    pool.map.side_effect = failure
    monkeypatch.setattr(executor_module, 'Pool', lambda: pool)
    writer = MagicMock()
    monkeypatch.setattr(type(solver), 'result_writer', writer)
    with pytest.raises(KeyboardInterrupt) as caught:
        solver.run(verbose=False, excel=True, file_path=tmp_path / 'unused.xlsx')
    assert caught.value is failure
    assert pool.__exit__.call_args.args[:2] == (KeyboardInterrupt, failure)
    writer.write.assert_not_called()
    assert capsys.readouterr().out == ''
