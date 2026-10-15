"""Small shared fixtures; the solver source is left unchanged."""

import numpy as np
import pytest

from tsp_pso.tsp_solver import TSPParticleSwarm
from tsp_pso.tspwr_solver import TSPWRParticleSwarm


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
    def make(**kwargs):
        options = dict(N=4, c1=2, distance_matrix=distance_matrix.copy())
        options.update(kwargs)
        if options.get("refuel_mode"):
            options.setdefault("prices", np.array([4., 2., 3., 5.]))
            options.setdefault("maxCapacity", 20)
            options.setdefault("consumption", 2)
        solver_class = TSPWRParticleSwarm if options.get("refuel_mode") else TSPParticleSwarm
        return solver_class(**options)
    return make


@pytest.fixture
def solver(make_solver):
    return make_solver()


def assert_permutation(route, size):
    assert route.shape == (size,)
    assert np.issubdtype(route.dtype, np.integer)
    np.testing.assert_array_equal(np.sort(route), np.arange(size))
