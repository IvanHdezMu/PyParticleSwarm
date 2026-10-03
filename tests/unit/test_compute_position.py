"""Direct calls to _compute_position, without Pool or multiprocessing."""

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from conftest import assert_permutation

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('ring, operator, expected_x, expected_iter, expected_fx', [
    (False, 1, [1,2,0,3], 1, 8), (False, 2, [2,3,0,1], 1, 2),
    (False, 3, [3,2,1,0], 1, -2), (False, 4, [3,2,0,1], 1, 4),
    (False, 5, [1,2,0,3], 2, 8),
    (True, 1, [0,1,2,3], 2, 5), (True, 2, [2,1,0,3], 1, 5),
    (True, 3, [0,1,2,3], 1, 5), (True, 4, [3,2,1,0], 2, 5),
    (True, 5, [3,0,1,2], 0, 5),
])
def test_compute_position_each_operator(solver, ring, operator, expected_x, expected_iter, expected_fx):
    solver.ring_mode = ring
    solver.k = 3
    route = np.array([0, 2, 1, 3])
    velocity = np.array([2., operator, 0.])
    original_velocity = velocity.copy()
    np.random.seed(7)
    x, n_iter, fx, vel = solver._compute_position((route, velocity, 3, solver._objective(route)))
    assert_array_equal(x, expected_x)
    assert n_iter == expected_iter
    assert fx == expected_fx == solver._objective(x)
    assert_array_equal(vel, original_velocity)
    assert_array_equal(velocity, original_velocity)
    assert_array_equal(route, [0, 2, 1, 3])
    assert_permutation(x, 4)
    assert solver.pos is None  # The worker returns state; it does not install it.


@pytest.mark.parametrize('operator', [1, 2, 3, 4, 5])
def test_compute_position_no_improvement_counts_candidates(make_solver, operator):
    s = make_solver(distance_matrix=np.ones((4, 4)) - np.eye(4))
    s.k = 3
    route = np.arange(4)
    velocity = np.array([2., operator, 0.])
    np.random.seed(7)
    x, n_iter, fx, vel = s._compute_position((route, velocity, 4, s._objective(route)))
    assert_array_equal(x, route)
    # Current <= loop evaluates budget + 1 candidates without improvements.
    assert n_iter == 7
    assert fx == -1 == s._objective(x)
    assert_array_equal(vel, [2, operator, 0])
    assert_array_equal(route, np.arange(4))
    assert_array_equal(velocity, [2, operator, 0])


@pytest.mark.parametrize('initial_iter, expected_x', [(0, [0,1,2,3]), (4, [1,3,0,2])])
def test_compute_position_reset_threshold(make_solver, initial_iter, expected_x):
    s = make_solver(distance_matrix=np.ones((4, 4)) - np.eye(4))
    s.k = 1
    route = np.arange(4)
    velocity = np.array([0., 4., 1.])
    np.random.seed(7)
    x, n_iter, fx, vel = s._compute_position((route, velocity, initial_iter, s._objective(route)))
    assert_array_equal(x, expected_x)
    assert n_iter == 1
    assert fx == -1 == s._objective(x)
    assert_array_equal(vel, [0, 4, 1])
    assert_array_equal(route, np.arange(4))
    assert_array_equal(velocity, [0, 4, 1])


def test_compute_position_negative_budget_is_noop(solver):
    route = np.arange(4)
    velocity = np.array([-1., 1., 0.])
    x, n_iter, fx, vel = solver._compute_position((route, velocity, 3, solver._objective(route)))
    assert_array_equal(x, route)
    assert n_iter == 3
    assert fx == -2 == solver._objective(x)
    assert_array_equal(vel, [-1, 1, 0])
    assert_array_equal(route, np.arange(4))


def test_compute_position_reset_recalculates_cost(solver):
    solver.k = 1  # identity operator isolates the reset's effect
    route = np.arange(4)
    velocity = np.array([0., 4., 1.])
    np.random.seed(7)
    x, n_iter, fx, vel = solver._compute_position((route, velocity, 4, solver._objective(route)))
    assert_array_equal(x, [1, 3, 0, 2])
    assert n_iter == 1
    assert fx == 13 == solver._objective(x)  # (8 + 7 + 9) - 11
    assert_array_equal(vel, [0, 4, 1])
    assert_array_equal(route, np.arange(4))
    assert_array_equal(velocity, [0, 4, 1])


@pytest.mark.parametrize('operator', [1, 2, 3, 4, 5])
def test_compute_position_refuel_no_improvement(make_solver, operator):
    # Equal prices/distances: all open routes consume 3 L costing 6.
    s = make_solver(refuel_mode=True, consumption=1, prices=np.full(4, 2.),
                    distance_matrix=np.ones((4, 4)) - np.eye(4))
    s.k = 3
    route = np.arange(4)
    velocity = np.array([2., operator, 0.])
    np.random.seed(7)
    x, n_iter, fx, vel = s._compute_position((route, velocity, 0, s._objective(route)))
    assert_array_equal(x, route)
    assert n_iter == 3
    assert fx == 2 == s._objective(x)  # lower bound 8, route cost 6
    assert_array_equal(vel, [2, operator, 0])
    assert_array_equal(route, np.arange(4))
    assert_array_equal(velocity, [2, operator, 0])
