"""Real process execution, external factories and worker failure propagation."""

from functools import partial
from multiprocessing import get_all_start_methods, get_context
import pickle
from unittest.mock import MagicMock

import numpy as np
import pytest

from tsp_pso.algorithms.core.pso_config import PSOConfig
from tsp_pso.algorithms.tsp.tsp_particle_swarm import TSPParticleSwarm
from tsp_pso.infrastructure.executors import particle_executor as executor_module
from tsp_pso.infrastructure.executors.particle_executor import ParticleExecutor

pytestmark = pytest.mark.functional
START_METHODS = ['spawn'] + (['forkserver'] if 'forkserver' in get_all_start_methods() else [])


class FailingParticleSwarm(TSPParticleSwarm):
    def _compute_position(self, args):
        raise RuntimeError('failure from worker')


@pytest.mark.parametrize('start_method', START_METHODS)
@pytest.mark.parametrize('refuel', [False, True])
def test_external_factory_and_serialization(monkeypatch, make_solver, start_method, refuel):
    solver = make_solver(refuel_mode=refuel, c1=6)
    monkeypatch.setattr(executor_module, 'Pool', partial(get_context(start_method).Pool, processes=2))
    executors = []
    workers = []

    class ParentExecutor(ParticleExecutor):
        def __reduce__(self):
            raise AssertionError('Active executor must not be serialized')

        def __enter__(self):
            super().__enter__()
            workers.extend(self._pool._pool)
            self.calls = 0
            return self

        def map(self, function, iterable):
            for obj in (solver, function):
                restored = pickle.loads(pickle.dumps(obj))
                state = vars(restored.__self__ if hasattr(restored, '__self__') else restored)
                assert 'particle_executor_factory' not in state
                assert not any(isinstance(value, ParticleExecutor) for value in state.values())
            self.calls += 1
            return super().map(function, iterable)

    # A local callable configured on the class is never part of the task pickle.
    def factory():
        executor = ParentExecutor()
        executors.append(executor)
        return executor

    monkeypatch.setattr(type(solver), 'particle_executor_factory', factory)
    route, score = solver.run(verbose=False, optType=3, permutReset=False)
    assert len(executors) == 1
    assert executors[0].calls == 3
    assert all(not worker.is_alive() for worker in workers)
    np.testing.assert_array_equal(np.sort(route), np.arange(solver.member_size))
    assert score == solver._objective(route)
    assert all(value is not executors[0] for value in vars(solver).values())


@pytest.mark.parametrize('start_method', START_METHODS)
def test_worker_failure_closes_pool_without_results(monkeypatch, distance_matrix, tmp_path,
                                                   capsys, start_method):
    workers = []
    pool_factory = get_context(start_method).Pool

    def tracked_pool():
        pool = pool_factory(processes=2)
        workers.extend(pool._pool)
        return pool

    monkeypatch.setattr(executor_module, 'Pool', tracked_pool)
    solver = FailingParticleSwarm(matrix=distance_matrix, config=PSOConfig(N=4, c1=2))
    writer = MagicMock()
    monkeypatch.setattr(FailingParticleSwarm, 'result_writer', writer)
    destination = tmp_path / 'unused.xlsx'
    with pytest.raises(RuntimeError, match='failure from worker'):
        solver.run(verbose=False, excel=True, file_path=destination)
    writer.write.assert_not_called()
    assert not destination.exists()
    assert capsys.readouterr().out == ''
    assert all(not worker.is_alive() for worker in workers)
