"""Small shared fixtures; the solver source is left unchanged."""

import numpy as np
import pytest

from tsp_pso.algorithms.core.pso_config import PSOConfig
from tsp_pso.algorithms.tspwr.refuel_config import RefuelConfig
from tsp_pso.algorithms.tsp.tsp_particle_swarm import TSPParticleSwarm
from tsp_pso.algorithms.tspwr.tspwr_particle_swarm import TSPWRParticleSwarm


@pytest.fixture(autouse=True)
def fixed_random_seed():
    state = np.random.get_state()
    np.random.seed(7)
    yield
    np.random.set_state(state)


@pytest.fixture
def distance_matrix():
    # Row minima: 2 + 2 + 3 + 4 = 11; maxima: 9 + 8 + 9 + 8 = 34.
    return np.array([[0, 2, 9, 7], [2, 0, 3, 8],
                     [9, 3, 0, 4], [7, 8, 4, 0]])


@pytest.fixture
def make_solver(distance_matrix):
    def make(*, refuel_mode=False, **kwargs):
        options = dict(N=4, c1=2, distance_matrix=distance_matrix.copy())
        options.update(kwargs)
        matrix = options.pop('distance_matrix')
        fuel = {}
        if refuel_mode:
            fuel = dict(
                prices=options.pop('prices', np.array([4., 2., 3., 5.])),
                refuel=RefuelConfig(
                    max_capacity=options.pop('maxCapacity', 20),
                    consumption=options.pop('consumption', 2),
                    full_init=options.pop('fullinit', False)))
        for old, new in [('resetThresholdDivisor', 'reset_threshold_divisor'),
                         ('primaryOperatorShare', 'primary_operator_share'),
                         ('progressWarmupMultiplier', 'progress_warmup_multiplier')]:
            if old in options:
                options[new] = options.pop(old)
        solver_class = TSPWRParticleSwarm if refuel_mode else TSPParticleSwarm
        return solver_class(matrix=matrix, config=PSOConfig(**options), **fuel)
    return make


@pytest.fixture
def solver(make_solver):
    return make_solver()


def assert_permutation(route, size):
    assert route.shape == (size,)
    assert np.issubdtype(route.dtype, np.integer)
    np.testing.assert_array_equal(np.sort(route), np.arange(size))
