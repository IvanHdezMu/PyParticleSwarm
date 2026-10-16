"""Solver classes and their problem-specific constructor arguments."""

from .tspwr.refuel_config import RefuelConfig
from .tsp.tsp_particle_swarm import TSPParticleSwarm
from .tspwr.tspwr_particle_swarm import TSPWRParticleSwarm


def tsp_arguments(experiment, prices, full):
    return {}


def tspwr_arguments(experiment, prices, full):
    return {
        'prices': prices,
        'refuel': RefuelConfig(
            max_capacity=experiment.max_capacity,
            consumption=experiment.consumption,
            full_init=full),
    }


# Each entry pairs a solver class with its argument builder.
# Builders receive (experiment, dataset_prices, initial_full_tank).
SOLVER_REGISTRY = {
    'tsp': (TSPParticleSwarm, tsp_arguments),
    'tspwr': (TSPWRParticleSwarm, tspwr_arguments),
}
