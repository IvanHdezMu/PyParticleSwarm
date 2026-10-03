"""Small real runs. Pool is limited to one worker with a fixed seed."""

from functools import partial
from multiprocessing import Pool

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose, assert_array_equal

import tsp_pso.solver as solver_module
from conftest import assert_permutation

pytestmark = pytest.mark.functional


@pytest.fixture(autouse=True)
def seeded_real_pool(monkeypatch):
    # Real subprocess and serialization, also reproducible on spawn platforms.
    monkeypatch.setattr(solver_module, 'Pool',
                        partial(Pool, processes=1, initializer=np.random.seed, initargs=(7,)))


def assert_consistent_result(s, result):
    route, cost = result
    n, nodes = s.swarm_size, s.member_size
    assert_permutation(route, nodes)
    assert cost == pytest.approx(s._objective(route))
    assert s.cur_steps > s.max_steps
    for name in ('pos', 'best', 'global_best'):
        values = getattr(s, name)
        assert values.shape == (n, nodes), name
        for member in values:
            assert_permutation(member, nodes)
    for name in ('fx', 'f_best', 'f_global_best', 'nIter'):
        assert getattr(s, name).shape == (n,), name
    assert s.vel.shape == (n, 3)
    assert np.all(np.isfinite(s.vel))
    assert np.all(s.nIter >= 0)
    assert_allclose(s.fx, [s._objective(member) for member in s.pos])
    assert_allclose(s.f_best, [s._objective(member) for member in s.best])
    assert_allclose(s.f_global_best, [s._objective(member) for member in s.global_best])
    assert np.all(s.f_best <= s.fx)
    assert np.all(np.diff(s.fx) >= 0)
    assert cost == pytest.approx(np.min(s.f_best))
    assert_allclose(s.f_global_best, cost)
    assert_array_equal(route, s.global_best[0])


@pytest.mark.parametrize('operator', [1, 2, 3, 4, 5, 10, 12, 15, 21])
@pytest.mark.parametrize('ring', [False, True])
@pytest.mark.parametrize('refuel', [False, True])
def test_run_all_modes(make_solver, operator, ring, refuel, capsys):
    s = make_solver(ring_mode=ring, refuel_mode=refuel)
    matrix = s.distance_matrix.copy()
    prices = s.prices.copy() if refuel else None
    np.random.seed(7)
    result = s.run(verbose=False, optType=operator, permutReset=False, k=3)
    assert_consistent_result(s, result)
    assert_array_equal(s.distance_matrix, matrix)
    if refuel:
        assert_array_equal(s.prices, prices)
    assert 'TERMINATING - REACHED MAXIMUM STEPS' in capsys.readouterr().out


@pytest.mark.parametrize('ring', [False, True])
@pytest.mark.parametrize('fullinit', [False, True])
def test_run_refuel_tank_and_resets(make_solver, ring, fullinit):
    s = make_solver(refuel_mode=True, ring_mode=ring, fullinit=fullinit)
    np.random.seed(7)
    result = s.run(verbose=False, optType=15, permutReset=True, minPermut=1, maxPermut=1, k=2)
    assert_consistent_result(s, result)
    assert_array_equal(s.vel[:, 2], np.ones(4))


@pytest.mark.parametrize('particles', [2, 6])
def test_run_particle_count_independent_of_nodes(make_solver, particles):
    s = make_solver(N=particles)
    np.random.seed(7)
    result = s.run(verbose=False, optType=3, permutReset=False, k=2)
    assert_consistent_result(s, result)

def test_rejects_single_particle(make_solver):
    with pytest.raises(ValueError, match='Number of particles must be at least 2'):
        make_solver(N=1)
        
def test_run_defaults(make_solver):
    s = make_solver()
    np.random.seed(7)
    assert_consistent_result(s, s.run())


def test_run_reinitializes_same_instance(solver):
    np.random.seed(7)
    first = solver.run(verbose=False, optType=3, permutReset=False, k=2)
    first_route, first_cost = first[0].copy(), first[1]
    assert_consistent_result(solver, first)
    solver.pos[:] = -1
    solver.nIter[:] = 999
    np.random.seed(7)
    second = solver.run(verbose=False, optType=3, permutReset=False, k=2)
    assert_consistent_result(solver, second)
    assert_array_equal(second[0], first_route)
    assert second[1] == first_cost


@pytest.mark.parametrize('refuel', [False, True])
def test_run_verbose_and_excel(make_solver, refuel, tmp_path, capsys):
    s = make_solver(c1=6, refuel_mode=refuel)
    destination = tmp_path / 'progress.xlsx'
    np.random.seed(7)
    result = s.run(verbose=True, optType=3, excel=True, file_path=destination, permutReset=False, k=2)
    assert_consistent_result(s, result)
    frame = pd.read_excel(destination)
    assert list(frame.columns) == ['Step', 'Result']
    assert frame.shape == (1, 2)
    assert frame['Step'].tolist() == [25]
    # Progress is recorded before updating best on the final iteration.
    assert np.isfinite(frame['Result'].iloc[0])
    assert frame['Result'].iloc[0] >= 0
    output = capsys.readouterr().out
    assert output.count('PARTICLE SWARM:') == 2
    assert ('BEST REFUEL COST:' if refuel else 'BEST DISTANCE:') in output


def test_run_excel_before_first_progress_record(solver, tmp_path):
    destination = tmp_path / 'empty_progress.xlsx'
    result = solver.run(verbose=False, excel=True, file_path=destination, permutReset=False, k=2)
    assert_consistent_result(solver, result)
    frame = pd.read_excel(destination)
    assert frame.empty
    assert list(frame.columns) == ['Step', 'Result']


def test_run_zero_iterations(solver):
    solver.max_steps = 0
    result = solver.run(verbose=False, permutReset=False, k=2)
    assert_consistent_result(solver, result)
    assert solver.cur_steps == 1
