"""Explicit candidates from each generator; reproducible order with seed 7."""

import inspect

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from conftest import assert_permutation

pytestmark = pytest.mark.unit

# Four-node routes. These lists intentionally include unchanged and duplicate
# candidates produced by the current operators.
CANDIDATES = [
    ('_two_opt_FLip', False, [[0,1,2,3], [0,2,1,3], [0,1,2,3], [2,1,0,3], [1,0,2,3], [0,1,2,3]]),
    ('_two_opt_FLip', True, [[0,2,1,3], [0,1,2,3], [0,1,2,3]]),
    ('_two_opt', False, [[0,1,3,2], [0,3,2,1], [0,2,1,3], [3,1,2,0], [2,1,0,3], [1,0,2,3]]),
    ('_two_opt', True, [[0,3,2,1], [0,2,1,3], [0,1,3,2]]),
    ('_two_and_a_half_opt', False, [[0,1,3,2], [0,2,3,1], [0,2,1,3], [1,2,3,0], [1,2,0,3], [1,0,2,3]]),
    ('_two_and_a_half_opt', True, [[0,1,3,2], [0,2,3,1], [0,2,1,3], [1,2,3,0], [1,2,0,3], [1,0,2,3]]),
    ('_k_opt_Flip', False, [[3,1,2,0], [0,3,2,1], [2,1,0,3], [3,1,2,0]]),
    ('_k_opt_Flip', True, [[3,1,2,0], [3,1,2,0], [0,3,2,1]]),
    ('_k_opt_Random', False, [[2,1,3,0], [0,3,2,1], [2,1,0,3], [1,0,2,3]]),
    ('_k_opt_Random', True, [[3,0,2,1], [0,1,3,2], [0,3,2,1]]),
]
OPERATORS = ['_two_opt_FLip', '_two_opt', '_two_and_a_half_opt', '_k_opt_Flip', '_k_opt_Random']


def generate(solver, name, route, k=3):
    return getattr(solver, name)(route, k) if name.startswith('_k_') else getattr(solver, name)(route)


@pytest.mark.parametrize('name, ring, expected', CANDIDATES)
def test_operator_exact_candidates(solver, name, ring, expected):
    solver.ring_mode = ring
    route = np.arange(4)
    np.random.seed(7)
    generator = generate(solver, name, route)
    assert inspect.isgenerator(generator)
    candidates = list(generator)
    assert len(candidates) == len(expected)
    for candidate, wanted in zip(candidates, expected):
        assert_array_equal(candidate, wanted)
        assert_permutation(candidate, 4)
        assert not np.shares_memory(candidate, route)
    assert_array_equal(route, np.arange(4))
    np.random.seed(7)
    assert_array_equal(list(generate(solver, name, route)), candidates)
    candidates[0][0] = -1
    assert_array_equal(route, np.arange(4))
    assert_array_equal(candidates[1], expected[1])


@pytest.mark.parametrize('name', OPERATORS)
@pytest.mark.parametrize('ring', [False, True])
def test_operator_single_node(solver, name, ring):
    solver.ring_mode = ring
    route = np.array([0])
    candidates = list(generate(solver, name, route, k=1))
    expected_count = 1 if name.startswith('_k_') and not ring else 0
    assert len(candidates) == expected_count
    for candidate in candidates:
        assert_array_equal(candidate, [0])
    assert_array_equal(route, [0])


@pytest.mark.parametrize('name', OPERATORS)
def test_operator_empty_path(solver, name):
    route = np.array([], dtype=int)
    assert list(generate(solver, name, route, k=1)) == []
    assert route.size == 0


@pytest.mark.parametrize('name', ['_k_opt_Flip', '_k_opt_Random'])
@pytest.mark.parametrize('ring', [False, True])
@pytest.mark.parametrize('k', [1, 4])
def test_k_opt_boundary_sizes(solver, name, ring, k):
    solver.ring_mode = ring
    route = np.arange(4)
    np.random.seed(7)
    candidates = list(generate(solver, name, route, k))
    assert len(candidates) == (3 if ring else 4)
    for candidate in candidates:
        assert_permutation(candidate, 4)
        if k == 1:
            assert_array_equal(candidate, route)
    assert_array_equal(route, np.arange(4))


@pytest.mark.parametrize('name', ['_k_opt_Flip', '_k_opt_Random'])
def test_k_opt_default_k_preserves_route_size(solver, name):
    # run() defaults to k=10, even for a four-node problem.
    route = np.arange(4)
    candidates = list(generate(solver, name, route, k=10))
    assert_array_equal(route, np.arange(4))
    for candidate in candidates:
        assert_permutation(candidate, 4)
