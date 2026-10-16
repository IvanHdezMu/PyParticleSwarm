"""Configuration defaults, immutability, serialization and legacy validation."""

from dataclasses import FrozenInstanceError, fields
import pickle

import numpy as np
import pytest

from tsp_pso.algorithms.solver_config import PSOConfig, RefuelConfig
from tsp_pso.algorithms.tsp_solver import TSPParticleSwarm
from tsp_pso.algorithms.tspwr_solver import TSPWRParticleSwarm

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('config', [
    PSOConfig(N=4, c1=2),
    RefuelConfig(max_capacity=20, consumption=2),
])
def test_configs_are_frozen_and_pickleable(config):
    restored = pickle.loads(pickle.dumps(config))
    assert restored == config
    assert type(restored) is type(config)
    for instance in (config, restored):
        for field in fields(instance):
            with pytest.raises(FrozenInstanceError):
                setattr(instance, field.name, None)
            with pytest.raises(FrozenInstanceError):
                delattr(instance, field.name)
    with pytest.raises(TypeError):
        config['prices'] = np.array([1., 2.])


def test_defaults_match_original_constructor(distance_matrix):
    config = PSOConfig(N=4, c1=2)
    assert config.ring_mode is False
    assert config.reset_threshold_divisor == 1000
    assert config.primary_operator_share == 0.2
    assert config.progress_warmup_multiplier == 5
    solver = TSPParticleSwarm(matrix=distance_matrix, config=config)
    assert solver.config is config
    assert solver.ring_mode is False
    assert solver.resetThresholdDivisor == 1000
    assert solver.primaryOperatorShare == 0.2
    assert solver.progressWarmupMultiplier == 5

    refuel = RefuelConfig()
    assert refuel.max_capacity is None
    assert refuel.consumption is None
    assert refuel.full_init is False
    with pytest.raises(ValueError, match='Unacceptable value for maxCapacity'):
        TSPWRParticleSwarm(matrix=distance_matrix, config=config,
                          prices=np.array([4., 2., 3., 5.]), refuel=refuel)
    with pytest.raises(ValueError, match='Unacceptable value for consumption'):
        TSPWRParticleSwarm(matrix=distance_matrix, config=config,
                          prices=np.array([4., 2., 3., 5.]),
                          refuel=RefuelConfig(max_capacity=20))


def test_numeric_conversion_does_not_mutate_config(distance_matrix):
    config = PSOConfig(N=4.9, c1=2.9)
    solver = TSPParticleSwarm(matrix=distance_matrix, config=config)
    assert solver.N == 4
    assert solver.c1 == 2
    assert solver.max_steps == 8
    assert config.N == 4.9
    assert config.c1 == 2.9
    assert solver.config is config


@pytest.mark.parametrize('value, message', [
    (None, 'Unacceptable value for N'),
    ('4', 'Unacceptable value for N'),
    (True, 'Number of particles must be at least 2'),
    (1.9, 'Number of particles must be at least 2'),
    (-1, 'Number of particles must be at least 2'),
])
def test_particle_validation_remains_in_solver(distance_matrix, value, message):
    config = PSOConfig(N=value, c1=2)
    with pytest.raises(ValueError, match=message):
        TSPParticleSwarm(matrix=distance_matrix, config=config)


def test_nonnumeric_c1_retains_existing_failure(distance_matrix):
    with pytest.raises(TypeError):
        TSPParticleSwarm(matrix=distance_matrix, config=PSOConfig(N=4, c1='2'))


@pytest.mark.parametrize('matrix, prices, fuel, message', [
    (np.zeros((2, 3)), [1], RefuelConfig(), 'Distance matrix must be square'),
    (np.zeros((2, 2)), [1], RefuelConfig(), 'Prices must have'),
    (np.zeros((2, 2)), [1, 2], RefuelConfig(), 'Unacceptable value for maxCapacity'),
    (np.zeros((2, 2)), [1, 2], RefuelConfig(max_capacity=20), 'Unacceptable value for consumption'),
    (np.zeros((2, 2)), [1, 2], RefuelConfig(max_capacity=20, consumption=2), 'Unacceptable value for N'),
])
def test_validation_order_is_preserved(matrix, prices, fuel, message):
    with pytest.raises(ValueError, match=message):
        TSPWRParticleSwarm(matrix=matrix, config=PSOConfig(N='invalid', c1=2),
                          prices=prices, refuel=fuel)
