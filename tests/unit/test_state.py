"""Constructor, representations, and mutations of explicitly prepared states."""

import numpy as np
import pytest
from numpy.testing import assert_array_equal, assert_allclose

pytestmark = pytest.mark.unit


def test_init(solver, distance_matrix):
    assert_array_equal(solver.distance_matrix, distance_matrix)
    assert (solver.N, solver.swarm_size, solver.member_size, solver.c1) == (4, 4, 4, 2)
    assert (solver.max_steps, solver.min_value, solver.max_value) == (8, 11, 34)
    assert (solver.ring_mode, solver.refuel_mode, solver.fullinit) == (False, False, False)
    for name in ('pos', 'best', 'global_best', 'fx', 'f_best', 'f_global_best',
                 'vel', 'nIter', 'cur_steps', 'k'):
        assert getattr(solver, name) is None


def test_init_refuel(make_solver, distance_matrix):
    prices = np.array([4., 2., 3., 5.])
    s = make_solver(refuel_mode=True, ring_mode=True, fullinit=True, prices=prices)
    assert (s.ring_mode, s.refuel_mode, s.fullinit) == (True, True, True)
    assert (s.maxCapacity, s.consumption, s.min_value, s.max_value) == (20, 2, 11, 85)
    assert_array_equal(prices, [4, 2, 3, 5])
    assert_array_equal(s.distance_matrix, distance_matrix)


@pytest.mark.parametrize('kwargs, message', [
    ({'distance_matrix': np.zeros((2, 3))}, 'Distance matrix must be square'),
    ({'refuel_mode': True, 'prices': [1, 2]}, 'Prices must have'),
    *[({'refuel_mode': True, 'maxCapacity': value}, 'Unacceptable value for maxCapacity')
      for value in (0, -1, '20', None)],
    *[({'refuel_mode': True, 'consumption': value}, 'Unacceptable value for consumption')
      for value in (0, -1, '2', None)],
])
def test_init_validation(make_solver, kwargs, message):
    with pytest.raises(ValueError, match=message):
        make_solver(**kwargs)


def test_init_float_c1_current_conversion(make_solver):
    s = make_solver(c1=2.9)
    assert s.c1 == 2
    assert s.max_steps == 8


@pytest.mark.parametrize('refuel, label, result', [(False, 'DISTANCE', 9), (True, 'REFUEL COST', 18)])
def test_str(make_solver, refuel, label, result):
    s = make_solver(refuel_mode=refuel)
    s.cur_steps = 7
    s.global_best = np.array([[0, 1, 2, 3]])
    assert str(s) == (f'PARTICLE SWARM: \nCURRENT STEPS: 7 \nBEST {label}: {result:.6f} \n'
                      'BEST MEMBER: [0 1 2 3] \n\n')
    assert s.cur_steps == 7
    assert_array_equal(s.global_best, [[0, 1, 2, 3]])


@pytest.mark.parametrize('refuel', [False, True])
def test_repr(make_solver, refuel):
    s = make_solver(refuel_mode=refuel)
    s.cur_steps = 7
    s.global_best = np.array([[0, 1, 2, 3]])
    assert repr(s) == str(s)


@pytest.mark.parametrize('refuel, result', [(False, 9), (True, 18)])
def test_data_to_save(make_solver, refuel, result):
    s = make_solver(refuel_mode=refuel)
    s.cur_steps = 7
    s.global_best = np.array([[0, 1, 2, 3]])
    assert s._dataToSave() == [7, result]
    assert_array_equal(s.global_best, [[0, 1, 2, 3]])
    assert s.cur_steps == 7


@pytest.mark.parametrize('reset', [False, True])
def test_clear_initialization_isolated(solver, monkeypatch, reset):
    # Isolate reset from sorting, which is tested independently below.
    calls = []
    monkeypatch.setattr(solver, '_global_best', lambda: calls.append(True))
    solver.pos = np.full((4, 4), -1)
    solver.nIter = np.full(4, 99)
    solver.cur_steps = 99
    np.random.seed(7)
    assert solver._clear(reset, .2, .8, 3) is None
    assert calls == [True]
    assert_array_equal(solver.pos, [[2, 1, 0, 3], [3, 1, 0, 2],
                                    [3, 1, 0, 2], [1, 0, 3, 2]])
    assert_array_equal(solver.fx, [1, 8, 8, 2])
    assert_array_equal(solver.nIter, np.zeros(4))
    assert_array_equal(solver.best, solver.pos)
    assert not np.shares_memory(solver.best, solver.pos)
    assert_array_equal(solver.f_best, solver.fx)
    assert not np.shares_memory(solver.f_best, solver.fx)
    assert_array_equal(solver.f_global_best, [34] * 4)
    assert_array_equal(solver.vel[:, 0], [4] * 4)
    assert_array_equal(solver.vel[:, 1], [1] * 4)
    assert_allclose(solver.vel[:, 2], [.35, .5, .65, .8] if reset else [0] * 4)
    assert (solver.k, solver.cur_steps) == (3, 1)


def test_clear_including_global_best(solver):
    np.random.seed(7)
    solver._clear(False, .2, .8, 3)
    assert_array_equal(solver.pos, [[2, 1, 0, 3], [1, 0, 3, 2],
                                    [3, 1, 0, 2], [3, 1, 0, 2]])
    assert_array_equal(solver.fx, [1, 2, 8, 8])
    assert_array_equal(solver.best, solver.pos)
    assert_array_equal(solver.global_best, [[2, 1, 0, 3]] * 4)
    assert_array_equal(solver.f_global_best, [1] * 4)


def test_best_updates_only_strict_improvements(solver):
    solver.pos = np.array([[0, 1, 2, 3], [1, 0, 2, 3], [2, 0, 1, 3], [3, 2, 1, 0]])
    solver.best = np.array([[3, 0, 1, 2]] * 4)
    solver.fx = np.array([2., 4., 6., 8.])
    solver.f_best = np.array([3., 4., 5., 10.])
    pos, fx = solver.pos.copy(), solver.fx.copy()
    assert solver._best() is None
    assert_array_equal(solver.f_best, [2, 4, 5, 8])
    assert_array_equal(solver.best, [pos[0], [3, 0, 1, 2], [3, 0, 1, 2], pos[3]])
    assert_array_equal(solver.pos, pos)
    assert_array_equal(solver.fx, fx)
    solver.pos[0, 0] = -1
    assert solver.best[0, 0] == 0


@pytest.fixture
def known_state(solver):
    solver.pos = np.array([[0, 1, 2, 3], [1, 0, 2, 3], [2, 0, 1, 3], [3, 2, 1, 0]])
    solver.best = solver.pos.copy()
    solver.fx = np.array([8., 2., 6., 4.])
    solver.f_best = np.array([7., 1., 5., 3.])
    solver.nIter = np.array([10, 20, 30, 40])
    solver.vel = np.array([[4, 1, .1], [8, 2, .2], [12, 3, .3], [16, 4, .4]])
    solver.global_best = np.array([[3, 0, 1, 2]] * 4)
    solver.f_global_best = np.full(4, 9.)
    return solver


def test_global_best_orders_and_updates(known_state):
    s = known_state
    assert s._global_best() is None
    assert_array_equal(s.pos, [[1, 0, 2, 3], [3, 2, 1, 0], [2, 0, 1, 3], [0, 1, 2, 3]])
    assert_array_equal(s.best, s.pos)
    assert_array_equal(s.fx, [2, 4, 6, 8])
    assert_array_equal(s.f_best, [1, 3, 5, 7])
    assert_array_equal(s.nIter, [20, 40, 30, 10])
    assert_array_equal(s.global_best, [[1, 0, 2, 3]] * 4)
    assert_array_equal(s.f_global_best, [1] * 4)


def test_global_best_preserves_particle_velocity_alignment(known_state):
    s = known_state
    before = s.vel.copy()
    s._global_best()
    assert_array_equal(s.vel, before[[1, 3, 2, 0]])


@pytest.mark.parametrize('previous', [0., 1.])
def test_global_best_does_not_replace_better_or_equal_record(known_state, previous):
    s = known_state
    s.f_global_best[:] = previous
    before = s.global_best.copy()
    s._global_best()
    assert_array_equal(s.global_best, before)
    assert_array_equal(s.f_global_best, [previous] * 4)

@pytest.mark.parametrize('mode, expected', [
    (1, [1]*5), (2, [2]*5), (3, [3]*5), (4, [4]*5), (5, [5]*5),
    (10, [1, 1, 2, 1, 1]), (12, [1, 2, 2, 2, 2]),
    (15, [1, 5, 5, 5, 5]), (21, [2, 1, 1, 1, 1]),
])
def test_opt_type(make_solver, mode, expected):
    s = make_solver(N=5)
    s.nIter = np.array([0, 2, 3, 4, 0])  # threshold is c1 == 2, strictly greater
    s.vel = np.array([[4, 1, .1], [4, 2, .2], [4, 1, .3], [4, 2, .4], [4, 5, .5]])
    before = s.vel.copy()
    assert s._Opt_Type(mode) is None
    assert_array_equal(s.vel[:, 1], expected)
    assert_array_equal(s.vel[:, [0, 2]], before[:, [0, 2]])
    assert_array_equal(s.nIter, [0, 2, 3, 4, 0])


def test_opt_type_unknown_current_behavior(solver):
    solver.nIter = np.zeros(4)
    solver.vel = np.array([[4, 1, .5]] * 4)
    before = solver.vel.copy()
    solver._Opt_Type(99)
    assert_array_equal(solver.vel, before)


def test_run_excel_requires_path_before_mutating(solver):
    with pytest.raises(ValueError, match='file_path is required when excel=True'):
        solver.run(excel=True)
    assert solver.pos is None
    assert solver.cur_steps is None
