import numpy as np

from .particle_swarm import ParticleSwarm


class TSPWRParticleSwarm(ParticleSwarm):
    _result_label = 'REFUEL COST'

    def __init__(self, N, c1, distance_matrix, ring_mode=False,
                 prices=None, maxCapacity=None, consumption=None, fullinit=False,
                 resetThresholdDivisor=1000, primaryOperatorShare=0.2, progressWarmupMultiplier=5):
        self.fullinit = fullinit
        self.prices = prices
        self.maxCapacity = maxCapacity
        self.consumption = consumption
        super().__init__(N, c1, distance_matrix, ring_mode,
                         resetThresholdDivisor, primaryOperatorShare, progressWarmupMultiplier)

    def _initialize_problem(self):
        if len(self.prices) != self.distance_matrix.shape[0]:
            raise ValueError('Prices must have as many values as there '
                             'are nodes in distance_matrix')
        if not (isinstance(self.maxCapacity, (int, float)) and self.maxCapacity > 0):
            raise ValueError('Unacceptable value for maxCapacity')
        if not (isinstance(self.consumption, (int, float)) and self.consumption > 0):
            raise ValueError('Unacceptable value for consumption')

    def _objective(self, member):
        return self._objectiveTSPWR(member)

    def _min_values(self):
        min_distance = self._min_distance()
        sorted_prices = np.sort(self.prices)
        return self._calculate_path_cost(min_distance, sorted_prices)

    def _max_values(self):
        max_distance = self._max_distance()
        reverse_sorted_prices = np.sort(self.prices)[::-1]
        return self._calculate_path_cost(max_distance, reverse_sorted_prices)

    def _dataToSave(self):
        return [self.cur_steps, self._calculate_refuel(self.global_best[0])]

    def _objectiveTSPWR(self, member):
        """
        Returns objective function for TSPWR

        Args:
        member: a member

        Returns:
        TSPWR objective function value of member
        """
        return abs(self.min_value-self._calculate_refuel(member)) 

    def _calculate_refuel(self, member):
        """
        Returns the total cost of fuel taking into account whether the ring mode is active
        and whether the tank was full at the start.

        Args:
        member: a member

        Returns:
        Total cost of fuel
        """

        if self.fullinit:
            tank = self.maxCapacity
        else:
            tank = 0.0
        cost = 0.0

        if self.ring_mode:
            member = np.append(member, member[0])

        path_price = self._path_prices(member)

        for i in range(len(member)-1): # In the last city it is never refuel
            distance_km = self.distance_matrix[member[i], member[i+1]]
            distance_liters = distance_km / self.consumption
            
            liters_aux = distance_liters
            for j in range(i+1, len(member)-1):
                if (path_price[j] < path_price[j+1]):
                    liters_aux += self.distance_matrix[member[j], member[j+1]] / self.consumption
                else:
                    break
            if liters_aux + tank > self.maxCapacity:
                liters_aux = self.maxCapacity - tank

            if (liters_aux > tank):
                cost += (liters_aux - tank) * path_price[i]
                tank += liters_aux - tank
                
            tank -= distance_liters
           
        return cost

    def _calculate_path_cost(self, km, sorted_prices):
        """
        Returns the cost of traveling a distance

        Args:
        km: kilometers traveled
        sorted_prices: array of prices of the path

        Return:
        Cost of fuel for the kilometers traveled
        """

        liters = km / self.consumption
        liters_aux = liters
        cost = 0
        for i in range(len(sorted_prices)):
            if liters_aux > self.maxCapacity:
                cost += self.maxCapacity * sorted_prices[i]
                liters_aux -= self.maxCapacity
            else:
                cost += liters_aux * sorted_prices[i]
                return cost
        return np.inf

    def _path_prices(self, path):
        """
        Returns the array of prices of the path

        Args:
        path: array of nodes

        Returns:
        Array of prices of the path
        """

        return self.prices[path]
