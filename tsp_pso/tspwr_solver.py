import numpy as np

from .base_solver import BaseParticleSwarm


class TSPWRParticleSwarm(BaseParticleSwarm):
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
