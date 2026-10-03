"""Calculations with independently hand-calculated expected results."""

import numpy as np
import pytest
from numpy.testing import assert_array_equal

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("ring, expected", [(False, 9), (True, 16)])
def test_calculate_distance(solver, ring, expected):
    solver.ring_mode = ring
    route = np.arange(4)
    matrix = solver.distance_matrix.copy()
    assert solver._calculate_distance(route) == expected  # 2 + 3 + 4 [+ 7]
    assert_array_equal(route, [0, 1, 2, 3])
    assert_array_equal(solver.distance_matrix, matrix)


@pytest.mark.parametrize("ring", [False, True])
def test_calculate_distance_single_node(solver, ring):
    solver.ring_mode = ring
    assert solver._calculate_distance(np.array([2])) == 0


def test_calculate_distance_empty_open_path(solver):
    assert solver._calculate_distance(np.array([], dtype=int)) == 0


def test_calculate_distance_directed(make_solver):
    s = make_solver(N=3, distance_matrix=np.array([[0, 2, 8], [7, 0, 3], [4, 9, 0]]))
    assert s._calculate_distance(np.array([0, 1, 2])) == 5
    assert s._calculate_distance(np.array([2, 1, 0])) == 16


@pytest.mark.parametrize("ring, expected", [(False, 2), (True, 5)])
def test_objective_tsp_absolute_difference(solver, ring, expected):
    solver.ring_mode = ring
    route = np.arange(4)
    assert solver._objectiveTSP(route) == expected  # abs(11 - (9 or 16))
    assert_array_equal(route, np.arange(4))


@pytest.mark.parametrize("refuel, expected", [(False, 2), (True, 7)])
def test_objective_dispatch(make_solver, refuel, expected):
    s = make_solver(refuel_mode=refuel)
    route = np.arange(4)
    assert s._objective(route) == expected
    assert_array_equal(route, np.arange(4))


@pytest.mark.parametrize("ring, full, expected", [
    (False, False, 18), (True, False, 35.5),
    (False, True, 0), (True, True, 0),
])
def test_calculate_refuel(make_solver, ring, full, expected):
    s = make_solver(refuel_mode=True, ring_mode=ring, fullinit=full)
    route = np.arange(4)
    matrix, prices = s.distance_matrix.copy(), s.prices.copy()
    # Empty tank: buy 4.5 L at node 0 for 18.
    # Closing the ring adds 3.5 L at node 3 for 17.5.
    assert s._calculate_refuel(route) == expected
    assert_array_equal(route, np.arange(4))
    assert_array_equal(s.distance_matrix, matrix)
    assert_array_equal(s.prices, prices)


@pytest.mark.parametrize("full, expected", [(False, 20), (True, 0)])
def test_calculate_refuel_three_nodes_hand_calculation(make_solver, full, expected):
    s = make_solver(N=3, distance_matrix=np.array([[0, 4, 10], [4, 0, 6], [10, 6, 0]]),
                    refuel_mode=True, prices=np.array([2., 3., 4.]),
                    consumption=1, maxCapacity=20, fullinit=full)
    # 4 + 6 = 10 L purchased at node 0 for 2 per litre, or free initial tank.
    route = np.arange(3)
    assert s._calculate_refuel(route) == expected
    assert_array_equal(route, [0, 1, 2])


def test_calculate_refuel_respects_capacity(make_solver):
    s = make_solver(N=3, distance_matrix=np.array([[0, 4, 5], [4, 0, 4], [5, 4, 0]]),
                    refuel_mode=True, prices=np.array([1., 2., 3.]),
                    consumption=1, maxCapacity=5)
    # Need 8 L total; capacity 5: buy 5 at price 1 then 3 at price 2.
    # Regression left failing if the solver buys all 8 L at the first node.
    assert s._calculate_refuel(np.arange(3)) == 11


@pytest.mark.parametrize("full", [False, True])
def test_calculate_refuel_single_node(make_solver, full):
    s = make_solver(refuel_mode=True, fullinit=full)
    assert s._calculate_refuel(np.array([1])) == 0


@pytest.mark.parametrize("ring, expected", [(False, 7), (True, 24.5)])
def test_objective_tspwr(make_solver, ring, expected):
    s = make_solver(refuel_mode=True, ring_mode=ring)
    route = np.arange(4)
    assert s.min_value == 11  # 11 km / 2 km/L * cheapest price 2.
    assert s._objectiveTSPWR(route) == expected
    assert_array_equal(route, np.arange(4))


@pytest.mark.parametrize("refuel, expected", [(False, [2, 9]), (True, [7, 23.5])])
def test_score(make_solver, refuel, expected):
    s = make_solver(refuel_mode=refuel)
    positions = np.array([[0, 1, 2, 3], [0, 2, 1, 3]])
    before = positions.copy()
    scores = s._score(positions)
    assert scores.shape == (2,)
    assert_array_equal(scores, expected)
    assert_array_equal(positions, before)


def test_score_one_member(solver):
    assert_array_equal(solver._score(np.array([[0, 1, 2, 3]])), [2])


@pytest.mark.parametrize("refuel, minimum, maximum", [(False, 11, 34), (True, 11, 85)])
def test_min_and_max_values(make_solver, refuel, minimum, maximum):
    s = make_solver(refuel_mode=refuel)
    matrix = s.distance_matrix.copy()
    prices = s.prices.copy() if refuel else None
    assert s._min_values() == minimum
    assert s._max_values() == maximum
    assert_array_equal(s.distance_matrix, matrix)
    if refuel:
        assert_array_equal(s.prices, prices)


def test_min_values_ignores_zero_rows(make_solver):
    s = make_solver(N=3, distance_matrix=np.array([[0, 0, 0], [0, 0, 2], [0, 2, 0]]))
    assert s._min_values() == 4
    assert s._max_values() == 4


def test_min_max_all_zero(make_solver):
    s = make_solver(distance_matrix=np.zeros((4, 4)))
    assert s._min_values() == 0
    assert s._max_values() == 0


@pytest.mark.parametrize("km, expected", [(0, 0), (6, 6), (10, 10), (14, 16), (30, 45)])
def test_calculate_path_cost(make_solver, km, expected):
    s = make_solver(refuel_mode=True, maxCapacity=5, consumption=2)
    prices = np.array([2., 3., 4.])
    assert s._calculate_path_cost(km, prices) == expected
    assert_array_equal(prices, [2., 3., 4.])


def test_calculate_path_cost_exhausted_prices_current_behavior(make_solver):
    s = make_solver(refuel_mode=True, maxCapacity=5, consumption=2)
    # Current behavior: no result if total demand exceeds all available tanks.
    assert s._calculate_path_cost(32, np.array([2., 3., 4.])) is None


@pytest.mark.parametrize("path, expected", [([3, 1, 0], [5, 2, 4]), ([2, 2], [3, 3]), ([], [])])
def test_path_prices(make_solver, path, expected):
    s = make_solver(refuel_mode=True)
    route = np.array(path, dtype=int)
    before = s.prices.copy()
    result = s._path_prices(route)
    assert_array_equal(result, expected)
    assert_array_equal(route, path)
    assert_array_equal(s.prices, before)
    if result.size:
        result[0] = -1
        assert_array_equal(s.prices, before)


def test_calculate_refuel_full_tank_then_purchase(make_solver):
    s = make_solver(N=3, distance_matrix=np.array([[0, 4, 5], [4, 0, 4], [5, 4, 0]]),
                    refuel_mode=True, prices=np.array([3., 2., 1.]),
                    consumption=1, maxCapacity=5, fullinit=True)
    # Start with 5 L, consume 4, buy the missing 3 L at price 2.
    route = np.arange(3)
    assert s._calculate_refuel(route) == 6
    assert_array_equal(route, [0, 1, 2])


def test_calculate_refuel_capacity_above_hardcoded_limit(make_solver):
    s = make_solver(N=2, distance_matrix=np.array([[0, 200], [200, 0]]),
                    refuel_mode=True, prices=np.array([1., 2.]),
                    consumption=1, maxCapacity=300)
    # A feasible 200 L leg in a 300 L tank must cost 200, not 150.
    assert s._calculate_refuel(np.array([0, 1])) == 200


def test_score_empty_swarm_current_behavior(solver):
    with pytest.raises(ValueError, match='Cannot apply_along_axis'):
        solver._score(np.empty((0, 4), dtype=int))


def test_calculate_path_cost_empty_prices_current_behavior(make_solver):
    s = make_solver(refuel_mode=True)
    assert s._calculate_path_cost(1, np.array([])) is None
