from .base_solver import BaseParticleSwarm


class TSPParticleSwarm(BaseParticleSwarm):
    _result_label = 'DISTANCE'

    def __init__(self, N, c1, distance_matrix, ring_mode=False, refuel_mode=False,
                 prices=None, maxCapacity=None, consumption=None, fullinit=False,
                 resetThresholdDivisor=1000, primaryOperatorShare=0.2, progressWarmupMultiplier=5):
        if bool(refuel_mode) is not False:
            raise ValueError("TSPParticleSwarm requires refuel_mode=False")
        self.refuel_mode = refuel_mode
        self.fullinit = fullinit
        super().__init__(N, c1, distance_matrix, ring_mode,
                         resetThresholdDivisor, primaryOperatorShare, progressWarmupMultiplier)

    def _objective(self, member):
        return self._objectiveTSP(member)

    def _min_values(self):
        return self._min_distance()

    def _max_values(self):
        return self._max_distance()

    def _dataToSave(self):
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

