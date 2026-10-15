"""Solver classes indexed by problem identifier."""

from .tsp_solver import TSPParticleSwarm
from .tspwr_solver import TSPWRParticleSwarm


SOLVER_REGISTRY = {
    'tsp': TSPParticleSwarm,
    'tspwr': TSPWRParticleSwarm,
}
