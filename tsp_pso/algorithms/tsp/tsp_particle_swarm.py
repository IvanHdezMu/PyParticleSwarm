from ..core.particle_swarm import ParticleSwarm
from ..core.pso_config import PSOConfig


class TSPParticleSwarm(ParticleSwarm):
    # Label for the physical measure returned by _dataToSave(), not the objective.
    _result_label = 'DISTANCE'

    def __init__(self, matrix, config: PSOConfig):
        super().__init__(matrix=matrix, config=config)

    def _objective(self, member):
        """Return the distance-based scalar objective to minimize."""
        return self._objectiveTSP(member)

    def _min_values(self):
        """Return the shared distance lower reference before swarm initialization."""
        return self._min_distance()

    def _max_values(self):
        """Return the shared distance upper reference before swarm initialization."""
        return self._max_distance()

    def _dataToSave(self):
        """Return [cur_steps, distance] for an initialized best route."""
        return [self.cur_steps, self._calculate_distance(self.global_best[0])]


    def _objectiveTSP(self, member):
        """
        Returns objective function for TSP

        Args:
        member: a member

        Returns:
        TSP objective function value of member
        """
        return self._calculate_distance(member) - self.min_value


    def _calculate_distance(self, member):
        """
        Returns the total distance traveled taking into account if the ring mode is active

        Args:
        member: a member

        Returns:
        Total distance traveled
        """

        total_distance = self.distance_matrix[member[:-1], member[1:]].sum()

        if self.ring_mode:
            total_distance += self.distance_matrix[member[-1], member[0]]

        return total_distance
