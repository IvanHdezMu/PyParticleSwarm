"""Solver classes and their problem-specific constructor arguments."""

from .tspwr.refuel_config import RefuelConfig
from .tsp.tsp_particle_swarm import TSPParticleSwarm
from .tspwr.tspwr_particle_swarm import TSPWRParticleSwarm


def tsp_arguments(prices, full, capacity, consumption):
    return {}


def tspwr_arguments(prices, full, capacity, consumption):
    return {
        'prices': prices,
        'refuel': RefuelConfig(
            max_capacity=capacity,
            consumption=consumption,
            full_init=full),
    }


# Each entry pairs a solver class with its argument builder.
# Builders receive only scientific values: prices, initial tank, capacity, consumption.
SOLVER_REGISTRY = {
    'tsp': (TSPParticleSwarm, tsp_arguments),
    'tspwr': (TSPWRParticleSwarm, tspwr_arguments),
}
