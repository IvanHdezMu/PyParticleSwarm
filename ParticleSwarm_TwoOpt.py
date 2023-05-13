from abc import ABCMeta, abstractmethod
from random import random
from numpy import apply_along_axis, argmin, array, copy, diag_indices_from, dot, zeros
from numpy.random import uniform

import numpy as np
from typing import Generator, List

"""
c1: constant for speed (recommended 0.1).
c2: ratio affecting partial best  
c3: ratio affecting the global best
c2 + c3 < 1 because 1-c2-c3 is the ratio affecting the initial velocity
""" 


class ParticleSwarm_TwoOpt:
    """
    Conducts particle swarm optimization
    """
    __metaclass__ = ABCMeta

    swarm_size = None
    member_size = None
    lower_bound = None
    upper_bound = None

    pos = None
    vel = None
    vel_new = None
    
    scores = None
    best = None
    global_best = None
    
    fx = None
    f_best = None
    f_global_best = None

    c1 = None
    c2 = None
    c3 = None

    cur_steps = None
    max_steps = None


    def __init__(self, swarm_size, c1, c2, c3, max_steps,distance_matrix,
                 TSPWR=False, prices=None, maxCapacity=None, consumption=None):
        """
        :param swarm_size: number of members in swarm
        :param c1: constant for 1st term in velocity calculation
        :param c2: contsant for 2nd term in velocity calculation
        :param c3: constant for 3rd term in velocity calculation
        :param max_steps: maximum steps to run algorithm for
        :param distance_matrix: distance matrix between nodes
        :param TSPWR: false->TSP mode active; true->TSPWR mode active
        :param prices = array with refueling prices
        :param maxCapacity = vehicle capacity in liters
        :param consumption = consumption of the vehicle in Km per liter
        """
        
        self.TSPWR = TSPWR
        
        self.distance_matrix = distance_matrix
        self.member_size = distance_matrix.shape[0]
        
        self.prices = prices
        self.maxCapacity = maxCapacity
        self.consumption = consumption
        
        
        self.min_value = self._min_values()
        self.max_value = self._max_values()
        
        
        if isinstance(swarm_size, int) and swarm_size > 0:
            self.swarm_size = swarm_size
        else:
            raise ValueError('Swarm size must be a positive integer')


        self.vel = np.ones(self.swarm_size) # [1.,1.,...,1.]


        if isinstance(c1, (int, float)) and isinstance(c2, (int, float)) and isinstance(c3, (int, float)):
            self.c1 = float(c1)
            self.c2 = float(c2)
            self.c3 = float(c3)
        else:
            raise ValueError()

        if isinstance(max_steps, int):
            self.max_steps = max_steps
        else:
            raise ValueError()


    def __str__(self):
        return ('PARTICLE SWARM: \n' +
                'CURRENT STEPS: %d \n' +
                'BEST FITNESS: %f \n' +
                'BEST MEMBER: %s \n\n') % \
               (self.cur_steps, self._objective(self.global_best[0]), str(self.global_best[0]))

    def __repr__(self):
        return self.__str__()

    def _clear(self):
        """
        Resets the variables that are altered on a per-run basis of the algorithm

        :return: None
        """
        aux = []
        for i in range(self.swarm_size):
            aux.append(np.random.choice(self.member_size,self.member_size,replace=False))
            
        self.pos = np.array(aux)
        self.fx = np.array(self._calculate_objective_arr(self.pos))
            
        self.scores = self._score(self.pos)
        self.best = copy(self.pos)
        self.f_best = np.array(self._calculate_objective_arr(self.best))
        
        self.cur_steps = 0
        self._global_best()

   
    def _objective(self, member):
        if self.TSPWR == False:
            return self._objectiveTSP(member)
        else:
            return self._objectiveTSPWR(member)
    
    def _objectiveTSP(self, member):
        """
        Returns objective function value for a member of swarm -
        operates on 1D numpy array

        :param member: a member
        :return: objective function value of member
        """
        total_distance = 0
        for i in range(len(member)-1): # no travel from last node
            current_node = member[i]
            next_node = member[i+1]
            # Sum of the distance to the next node
            total_distance += self.distance_matrix[current_node, next_node]
             
        return abs(self.min_value-total_distance)
    
    def _objectiveTSPWR(self, member):
        """
        Returns objective function value for a member of swarm -
        operates on 1D numpy array

        :param member: a member
        :return: objective function value of member
        """
        tank = 0.0
        cost = 0.0
        path_price = self._path_prices(member)     
        for i in range(len(member)-1): # In the last city it is never refuel
            distance_km = self.distance_matrix[member[i]][member[i+1]]
            distance_liters = distance_km / self.consumption
            
            liters_aux = distance_liters
            if (i <= len(member)-2):
                for j in range(i+1, len(member)-1):
                    if (path_price[j] < path_price[j+1]):
                        liters_aux += self.distance_matrix[member[j]][member[j+1]] / self.consumption
                    else:
                        break
                if liters_aux + tank > 150.0:
                    liters_aux = 150.0 - tank

            if (liters_aux > tank):
                cost += (liters_aux - tank) * path_price[i]
                tank += liters_aux - tank
                
            tank -= distance_liters
             
        return abs(self.min_value-cost)

    def _score(self, pos):
        """
        Applies objective function to all members of swarm

        :param pos: position matrix
        :return: score vector
        """
        return apply_along_axis(self._objective, 1, pos)

    def _best(self, old, new):
        """
        Finds the best objective function values for each member of swarm

        :param old: old values
        :param new: new values
        :return: None
        """
        old_scores = self._score(old)
        new_scores = self._score(new)
        best = []
        for i in range(len(old_scores)):
            if old_scores[i] < new_scores[i]:
                best.append(old[i])
            else:
                best.append(new[i])
                self.f_best[i] = self._objective(self.best[i])
        self.best = array(best)

    def _global_best(self):
        """
        Finds the global best across swarm

        :return: None
        """
        if self.global_best is None or min(self.scores) < self._objective(self.global_best[0]):
            self.global_best = array([self.pos[argmin(self.scores)]] * self.swarm_size)
            self.f_global_best = np.full(self.swarm_size, self._objective(self.global_best[0]))

    def run(self, verbose=True):
        """
        Conducts particle swarm optimization

        :param verbose: indicates whether or not to print progress regularly
        :return: best member of swarm and objective function value of best member of swarm
        """
        self._clear()
        for i in range(self.max_steps):
            self.cur_steps += 1

            if verbose and ((i + 1) % 100 == 0):
                print(self)



            aux_vel =  self.vel * (1-self.c2-self.c3) + (self.fx-self.f_best)/self.fx * self.c2 +  (self.fx-self.f_global_best)/self.fx * self.c3     
            self.vel_new = (self.c1 * i * aux_vel / self.max_steps)

            pos_new = self._compute_position() #self.pos + vel_new

            self._best(self.pos, pos_new)
            self.pos = pos_new
            self.scores = self._score(self.pos)
            self._global_best()


        print("TERMINATING - REACHED MAXIMUM STEPS")
        return self.global_best[0], self._objective(self.global_best[0])

    def _calculate_objective_arr(self, x):
        
        n_particles = x.shape[0]  # number of particles
        
        fx = []
        for i in range(n_particles):
            fx.append(self._objective(x[i])) 
            
        return fx

    def _compute_position(self):
        """Update the position of the swarm
        This computes the next position in a discrete swarm.
        """
        
        x = self.pos
        n_particles = x.shape[0]  # number of particles
                                     
        for i in range(n_particles):

            xn = next (self._two_opt_gen(x[i].tolist()))
            fn =  self._objective(xn)              

            if self._acceptance_rule(self.fx[i], fn, np.mean(self.vel_new[i])):
                x[i], self.fx[i] = xn, fn                
                    
        return x
    
    def _two_opt_gen(self, x: List[int]) -> Generator[List[int], List[int], None]:
    #def _two_opt_gen(self, x: np.array) -> Generator[np.array, np.array, None]:
        """2-opt perturbation scheme [2]"""
        n = len(x)
        i_range = range(2, n)
        for i in np.random.choice(i_range, len(i_range), replace=False):
            j_range = range(i + 1, n + 1)
            for j in np.random.choice(j_range, len(j_range), replace=False):
                xn = x.copy()
                xn = xn[:i - 1] + list(reversed(xn[i - 1:j])) + xn[j:]
                yield xn
    
    def _acceptance_rule(self, fx: float, fn: float, velocity: float):
        """Metropolis acceptance rule
        
        fx: current value
        fn: proposed value
        velocity: constant that controls the acceptance rate of the new samples
        """
    
        dfx = fn - fx
        if (dfx < 0):
            return True
        else:
            dif_max = self.max_value - self.min_value
            aux = (dif_max - dfx) / dif_max
            if (np.random.rand() <= np.exp(-aux / velocity)):
                return True
            else:
                return False
    
    def _min_values(self):
        min_distance = 0
        for raw in self.distance_matrix:
            non_zero_values = [value for value in raw if value != 0]
            if non_zero_values:        
                min_distance += min(non_zero_values)
                
        if self.TSPWR == False:
            return min_distance
        else:
            sorted_prices = np.sort(self.prices)
            return self._calculate_path_cost(min_distance, sorted_prices)
               

    def _max_values(self):
        max_distance = 0
        for raw in self.distance_matrix:
            max_distance += max(raw)
            
        if self.TSPWR == False:
            return max_distance
        else:
            sorted_prices = np.sort(self.prices)[::-1]
            return self._calculate_path_cost(max_distance, sorted_prices)

    def _calculate_path_cost(self, km, sorted_prices):
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
            
    
    def _path_prices(self, path): # array of prices of the path
        prices_arr = np.zeros(len(path))
        for i in range(len(path)):
            prices_arr[i] = self.prices[path[i]]
        return prices_arr