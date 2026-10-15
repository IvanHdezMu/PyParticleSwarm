"""Backward-compatible construction of the appropriate particle swarm class."""

from .tsp_solver import TSPParticleSwarm
from .tspwr_solver import TSPWRParticleSwarm


def ParticleSwarm_VarOptMultiprocess(
        N, c1, distance_matrix, ring_mode=False, refuel_mode=False,
        prices=None, maxCapacity=None, consumption=None, fullinit=False,
        resetThresholdDivisor=1000, primaryOperatorShare=0.2, progressWarmupMultiplier=5):
    """Preserve legacy constructor arguments; return a specialized solver instance."""
    solver_class = TSPWRParticleSwarm if refuel_mode else TSPParticleSwarm
    return solver_class(
        N, c1, distance_matrix, ring_mode, refuel_mode, prices, maxCapacity,
        consumption, fullinit, resetThresholdDivisor, primaryOperatorShare,
        progressWarmupMultiplier)
