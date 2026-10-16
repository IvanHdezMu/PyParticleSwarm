"""Specialized construction and serialization."""

import pickle

import numpy as np
import pytest

from tsp_pso.algorithms.solver_config import PSOConfig, RefuelConfig

from tsp_pso.algorithms.particle_swarm import ParticleSwarm
from tsp_pso.algorithms.tsp_solver import TSPParticleSwarm
from tsp_pso.algorithms.tspwr_solver import TSPWRParticleSwarm

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('solver_class, refuel, expected', [
    (TSPParticleSwarm, False, -2), (TSPWRParticleSwarm, True, 7),
])
def test_specialized_defaults(distance_matrix, solver_class, refuel, expected):
    fuel = dict(prices=np.array([4., 2., 3., 5.]), refuel=RefuelConfig(max_capacity=20, consumption=2)) if refuel else {}
    solver = solver_class(matrix=distance_matrix, config=PSOConfig(N=4, c1=2), **fuel)
    assert not hasattr(solver, 'refuel_mode')
    assert isinstance(solver.config, PSOConfig)
    assert solver._objective(np.arange(4)) == expected


@pytest.mark.parametrize('solver_class, refuel', [
    (TSPParticleSwarm, True), (TSPWRParticleSwarm, False),
])
def test_specialized_constructor_rejects_obsolete_mode(distance_matrix, solver_class, refuel):
    with pytest.raises(TypeError, match='refuel_mode'):
        solver_class(matrix=distance_matrix, config=PSOConfig(N=4, c1=2), refuel_mode=refuel)


@pytest.mark.parametrize('positional', [False, True])
@pytest.mark.parametrize('refuel, solver_class, expected', [
    (False, TSPParticleSwarm, -2), (True, TSPWRParticleSwarm, 7),
])
def test_specialized_constructor_and_pickle(distance_matrix, positional, refuel, solver_class, expected):
    config = PSOConfig(N=4, c1=2, reset_threshold_divisor=500,
                       primary_operator_share=0.4, progress_warmup_multiplier=3)
    options = dict(matrix=distance_matrix, config=config)
    if refuel:
        options.update(prices=np.array([4., 2., 3., 5.]),
                       refuel=RefuelConfig(max_capacity=20, consumption=2))
    if positional:
        solver = solver_class(*options.values())
    else:
        solver = solver_class(**options)
    restored = pickle.loads(pickle.dumps(solver))
    for instance in (solver, restored):
        assert type(instance) is solver_class
        assert instance.config == config
        if refuel:
            assert instance.refuel == options['refuel']
            assert 'prices' not in vars(instance.refuel)
        else:
            assert not hasattr(instance, 'refuel')
        assert not hasattr(instance, 'refuel_mode')
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

    solver = ConstantSwarm(matrix=distance_matrix, config=PSOConfig(N=4, c1=2))
    solver._clear(False, 0.2, 0.8, 3)
    assert solver._dataToSave() == [1, 3]
    assert 'BEST CONSTANT: 3.000000' in str(solver)
    np.testing.assert_array_equal(solver.fx, [3] * 4)
    for attribute in ('refuel_mode', 'prices', 'maxCapacity', 'consumption', 'fullinit'):
        assert not hasattr(solver, attribute)


@pytest.mark.parametrize('parameter', ['prices', 'refuel', 'maxCapacity', 'consumption', 'fullinit'])
def test_tsp_rejects_fuel_arguments(distance_matrix, parameter):
    with pytest.raises(TypeError, match=parameter):
        TSPParticleSwarm(matrix=distance_matrix, config=PSOConfig(N=4, c1=2), **{parameter: None})


def test_refuel_state_is_ready_before_bounds(monkeypatch, distance_matrix):
    original = TSPWRParticleSwarm._initialize_problem
    calls = []

    def validate(solver):
        assert solver.prices.tolist() == [4., 2., 3., 5.]
        assert solver.maxCapacity == 20
        assert solver.consumption == 2
        assert solver.fullinit is True
        assert solver.refuel == RefuelConfig(max_capacity=20, consumption=2, full_init=True)
        assert solver.config == PSOConfig(N=4, c1=2)
        assert solver.distance_matrix is distance_matrix
        assert not hasattr(solver, 'min_value')
        assert not hasattr(solver, 'max_value')
        calls.append('validation')
        original(solver)

    monkeypatch.setattr(TSPWRParticleSwarm, '_initialize_problem', validate)
    solver = TSPWRParticleSwarm(
        matrix=distance_matrix, config=PSOConfig(N=4, c1=2),
        prices=np.array([4., 2., 3., 5.]),
        refuel=RefuelConfig(max_capacity=20, consumption=2, full_init=True))
    assert calls == ['validation']
    assert (solver.min_value, solver.max_value) == (11, 85)
