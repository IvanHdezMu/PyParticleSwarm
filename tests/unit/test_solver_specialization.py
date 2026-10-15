"""Specialized construction and serialization."""

import pickle

import numpy as np
import pytest

from tsp_pso.particle_swarm import ParticleSwarm
from tsp_pso.tsp_solver import TSPParticleSwarm
from tsp_pso.tspwr_solver import TSPWRParticleSwarm

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('solver_class, refuel, expected', [
    (TSPParticleSwarm, False, -2), (TSPWRParticleSwarm, True, 7),
])
def test_specialized_defaults(distance_matrix, solver_class, refuel, expected):
    solver = solver_class(4, 2, distance_matrix, prices=np.array([4., 2., 3., 5.]),
                          maxCapacity=20, consumption=2)
    assert solver.refuel_mode is refuel
    assert solver._objective(np.arange(4)) == expected


@pytest.mark.parametrize('solver_class, refuel', [
    (TSPParticleSwarm, True), (TSPWRParticleSwarm, False),
])
def test_specialized_constructor_rejects_conflicting_mode(distance_matrix, solver_class, refuel):
    with pytest.raises(ValueError, match='requires refuel_mode='):
        solver_class(4, 2, distance_matrix, refuel_mode=refuel)


@pytest.mark.parametrize('positional', [False, True])
@pytest.mark.parametrize('refuel, solver_class, expected', [
    (False, TSPParticleSwarm, -2), (True, TSPWRParticleSwarm, 7),
])
def test_specialized_constructor_and_pickle(distance_matrix, positional, refuel, solver_class, expected):
    options = dict(N=4, c1=2, distance_matrix=distance_matrix, ring_mode=False,
                   refuel_mode=refuel, prices=np.array([4., 2., 3., 5.]),
                   maxCapacity=20, consumption=2, fullinit=False,
                   resetThresholdDivisor=500, primaryOperatorShare=0.4,
                   progressWarmupMultiplier=3)
    if positional:
        solver = solver_class(*options.values())
    else:
        solver = solver_class(**options)
    restored = pickle.loads(pickle.dumps(solver))
    for instance in (solver, restored):
        assert type(instance) is solver_class
        assert instance.refuel_mode is refuel
        assert instance._objective(np.arange(4)) == expected
        assert instance.resetThresholdDivisor == 500
        assert instance.primaryOperatorShare == 0.4
        assert instance.progressWarmupMultiplier == 3


def test_base_supports_problem_independent_objective(distance_matrix):
    class ConstantSwarm(ParticleSwarm):
        _result_label = 'CONSTANT'

        def _objective(self, member):
            return 3

        def _min_values(self):
            return 0

        def _max_values(self):
            return 10

        def _dataToSave(self):
            return [self.cur_steps, self._objective(self.global_best[0])]

    solver = ConstantSwarm(4, 2, distance_matrix)
    solver._clear(False, 0.2, 0.8, 3)
    assert solver._dataToSave() == [1, 3]
    assert 'BEST CONSTANT: 3.000000' in str(solver)
    np.testing.assert_array_equal(solver.fx, [3] * 4)
    for attribute in ('refuel_mode', 'prices', 'maxCapacity', 'consumption', 'fullinit'):
        assert not hasattr(solver, attribute)
