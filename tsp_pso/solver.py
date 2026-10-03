# -*- coding: utf-8 -*-
"""
Created on Fri May 26 17:37:31 2023

@author: Ivan Hernandez Muñoz

Algorithm based on Solid's ParticleSwarm (Python framework for gradient-free optimization)
"""

import numpy as np
from typing import Generator
from multiprocessing import Pool
import pandas as pd

class ParticleSwarm_VarOptMultiprocess:
    """
    Particle swarm
    """
    
    swarm_size = None
    member_size = None

    pos = None
    best = None
    global_best = None
    
    fx = None
    f_best = None
    f_global_best = None
    
    vel = None
    nIter = None

    N = None
    c1 = None
    k = None
    v = None

    cur_steps = None
    
    def __init__(self, N, c1, distance_matrix, ring_mode=False, refuel_mode=False,
                 prices=None, maxCapacity=None, consumption=None, fullinit=False):
        """
        Initialization function

        Args:
        N: Number of particles
        C1: x Number of nodes = max steps
        distance_matrix: distance between nodes
        ring_mode: add distance from the last node to the first node
        refuel_mode: false->TSP mode active; true->TSPWR mode active
        prices: array with refueling prices
        maxCapacity: vehicle capacity in liters
        consumption: consumption of the vehicle in Km per liter
        fullinit: full tank at first

        Returns:
        None
        """
        
        if distance_matrix.shape[0] == distance_matrix.shape[1]:
            self.distance_matrix = distance_matrix
        else:
            raise ValueError('Distance matrix must be square')
        
        self.ring_mode = ring_mode

        self.fullinit = fullinit
        
        self.refuel_mode = refuel_mode
        if refuel_mode: 
            
            if len(prices) == distance_matrix.shape[0]:
                self.prices = prices
            
                if isinstance(maxCapacity, (int, float)) and maxCapacity > 0:
                    self.maxCapacity = maxCapacity
                else:
                    raise ValueError('Unacceptable value for maxCapacity')
                    
                if isinstance(consumption, (int, float)) and consumption > 0:
                    self.consumption = consumption
                else:
                    raise ValueError('Unacceptable value for consumption')  
            else:
                raise ValueError('Prices must have as many values as there '
                 'are nodes in distance_matrix')

        if isinstance(N, (int, float)):
            self.N = int(N)

            if self.N < 2:
                raise ValueError('Number of particles must be at least 2')
        else:
            raise ValueError('Unacceptable value for N')

        if isinstance(c1, (int, float)):
            self.c1 = int(c1)
        
        self.min_value = self._min_values()
        self.max_value = self._max_values()
            
        self.member_size = distance_matrix.shape[0]

        self.swarm_size = self.N
        
        # max_steps
        self.max_steps = self.c1 * self.member_size
                      
        
    def __str__(self):
        """
        Special method to return a string representation of a class instance depending on whether it is TSP or TSPWR

        Returns:
        String representative of the best result achieved by the swarm
        """
        if not self.refuel_mode:
            return ('PARTICLE SWARM: \n' +
                    'CURRENT STEPS: %d \n' +
                    'BEST DISTANCE: %f \n' +
                    'BEST MEMBER: %s \n\n') % \
                   (self.cur_steps, self._calculate_distance(self.global_best[0]), str(self.global_best[0]))
        else:
            return ('PARTICLE SWARM: \n' +
                    'CURRENT STEPS: %d \n' +
                    'BEST REFUEL COST: %f \n' +
                    'BEST MEMBER: %s \n\n') % \
                   (self.cur_steps, self._calculate_refuel(self.global_best[0]), str(self.global_best[0]))                   

    def __repr__(self):
        """
        Special method used to represent a class’s objects as a string

        Returns:
        Response of the __str__ funtion
        """
        return self.__str__()        
        
    def _clear(self, permutReset, minPermut, maxPermut, k):
        """
        Resets the variables that are modified in each execution of the algorithm

        Args:
        permutReset: probability of permutation
        minPermut: minimum probability value
        maxPermut: maximum probability value
        k: k constant for k-Opt algorithms

        Returns:
        None
        """
        self.k = k

        aux = []
        for i in range(self.swarm_size):
            aux.append(np.random.choice(self.member_size,self.member_size,replace=False))
        self.pos = np.array(aux) 
            
        self.fx = self._score(self.pos)   
        self.nIter = np.zeros(self.swarm_size)

        vel0 = np.full(self.swarm_size, self.member_size, dtype=int)
        vel1 = np.ones(self.swarm_size)
        if permutReset:
            aux_vel2 = np.arange(1, self.swarm_size + 1)
            vel2 = np.interp(aux_vel2, [0, self.swarm_size], [minPermut, maxPermut])  # Random probability
        else:
            vel2 = np.zeros(self.swarm_size)
        self.vel = np.column_stack((vel0, vel1, vel2))

        self.best = np.copy(self.pos)
        
        self.global_best = self.best # only because of the size
        self.f_global_best = np.ones(self.swarm_size) * self.max_value
        self.f_best = self.fx.copy()
        
        self.cur_steps = 1
        self._global_best()
            
     
    def _objective(self, member):
        """
        Returns objective function value for a member of swarm depending on whether it is TSP or TSPWR

        Args:
        member: a member

        Returns:
        Objective function value of member
        """
        if not self.refuel_mode:
            return self._objectiveTSP(member)
        else:
            return self._objectiveTSPWR(member)
    
    def _objectiveTSP(self, member):
        """
        Returns objective function for TSP

        Args:
        member: a member

        Returns:
        TSP objective function value of member
        """
        return abs(self.min_value-self._calculate_distance(member))
    
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

    def _score(self, pos):
        """
        Applies objective function to all members of swarm

        :param pos: position matrix
        :return: score vector
        """
        return np.apply_along_axis(self._objective, 1, pos)

    def _best(self):
        """
        Copy the results ,and their positions, of those who improve the local best

        :return: None
        """
        indexes = np.where(self.fx < self.f_best)
        self.f_best[indexes] = self.fx[indexes]
        self.best[indexes] = self.pos[indexes]

    def _global_best(self):
        """
        Finds the global best across swarm and orders arrays

        :return: None
        """
        ordered_indexes = np.argsort(self.fx)
        if np.any(ordered_indexes):
            self.f_best = self.f_best[ordered_indexes]
            self.best = self.best[ordered_indexes]
            self.pos = self.pos[ordered_indexes]
            self.fx = self.fx[ordered_indexes]
            self.nIter = self.nIter[ordered_indexes]
            self.vel = self.vel[ordered_indexes]
            
            min_index = np.argmin(self.f_best)    
            if self.f_best[min_index] < self.f_global_best[0]:
                self.f_global_best[0:] = self.f_best[min_index]
                self.global_best[0:] = self.best[min_index]

                  
            
    def _min_values(self):
        """
        TSP: Minimum distance calculation
        TSPWR: Minimum price calculation
        """
        min_distance = 0
        for raw in self.distance_matrix:
            non_zero_values = [value for value in raw if value != 0]
            if non_zero_values:        
                min_distance += min(non_zero_values)
                
        if not self.refuel_mode:
            return min_distance
        else:
            sorted_prices = np.sort(self.prices)
            return self._calculate_path_cost(min_distance, sorted_prices)
               

    def _max_values(self):
        """
        TSP: Maximum distance calculation
        TSPWR: Maximum price calculation
        """
        max_distance = 0
        for raw in self.distance_matrix:
            max_distance += max(raw)
            
        if not self.refuel_mode:
            return max_distance
        else:
            reverse_sorted_prices = np.sort(self.prices)[::-1]
            return self._calculate_path_cost(max_distance,
                                             reverse_sorted_prices)

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

    def _path_prices(self, path):
        """
        Returns the array of prices of the path

        Args:
        path: array of nodes

        Returns:
        Array of prices of the path
        """

        return self.prices[path]

    def run(self, verbose=True, optType=10, excel=False, file_path=None,
            permutReset=True, minPermut=0.2, maxPermut=0.8, k=10):
        """
        Particle swarm optimization

        Args:
        verbose: indicates whether or not to print progress regularly
        optType: type of algorithm or combination of algorithms for searches
        excel: indicates whether or not to save progress regularly
        file_path: required destination when excel is enabled
        permutReset: probability of permutation
        minPermut: minimum probability value
        maxPermut: maximum probability value
        k: k constant for k-Opt algorithms

        Returns:
        The best member of swarm and its objective function value
        """
        if excel and file_path is None:
            raise ValueError('file_path is required when excel=True')
        self._clear(permutReset, minPermut, maxPermut, k)
        
        output_list = []
        aux_n_steps = 1
        
        with Pool() as p:
            while self.cur_steps <= self.max_steps:

                self.vel[:,0] = self.member_size * aux_n_steps
                self._Opt_Type(optType)

                results = p.map(self._compute_position, zip(self.pos, self.vel, self.nIter, self.fx))

                pos, nIter, fx, vel = zip(*results)
                self.pos = np.array(pos)
                self.nIter = np.array(nIter)
                self.fx = np.array(fx)
                self.vel = np.array(vel)

                self.cur_steps += self.vel[0, 0]

                if self.cur_steps > self.member_size * 5:
                    if verbose:
                        print(self)
                    if excel:
                        output_list.append(self._dataToSave())

                aux_n_steps += 1

                self._best()
                self._global_best()

        if excel:
            columns = ['Step', 'Result']
            df = pd.DataFrame(output_list, columns=columns)
            df.to_excel(file_path, index=False)

        print("TERMINATING - REACHED MAXIMUM STEPS")
        print(self)
        return self.global_best[0], self._objective(self.global_best[0])

    def _dataToSave(self):
        """
        Return a string representation of a class instance depending on whether it is TSP or TSPWR

        Returns:
        String representative of the best result achieved by the swarm
        """
        if not self.refuel_mode:
            return [self.cur_steps, self._calculate_distance(self.global_best[0])]
        else:
            return [self.cur_steps, self._calculate_refuel(self.global_best[0])]

    def _Opt_Type(self, optType):
        """
        Returns the type of simple algorithm depending on the search

        Args:
        optType: type of algorithm or combination of algorithms. Possible values:
            1 = 2-Opt con Flip
            2 = 2,5-Opt
            3 = 2-Opt
            4 = k-Opt FLip
            5 = k-Opt Random
            10 = 2-Opt Flip + 2,5-Opt (change)
            12 = 2-Opt Flip + 2,5-Opt (20-80)
            15 = 2-Opt Flip + k-Opt Random (20-80)
            21 = 2,5-Opt + 2-Opt Flip (20-80)

        Returns:
        None
        """

        for i, nIter in enumerate(self.nIter):
            if optType <= 5:
                    self.vel[i, 1] = optType
            elif optType == 10:
                if nIter > (self.max_steps / self.member_size):
                    if self.vel[i, 1] == 1:
                        self.vel[i, 1] = 2
                    else:
                        self.vel[i, 1] = 1
                else:
                    self.vel[i, 1] = 1
            elif optType == 12:
                    if i < (self.swarm_size * 0.2):
                        self.vel[i, 1] = 1
                    else:
                        self.vel[i, 1] = 2
            elif optType == 15:
                    if i < (self.swarm_size * 0.2):
                        self.vel[i, 1] = 1
                    else:
                        self.vel[i, 1] = 5
            elif optType == 21:
                    if i < (self.swarm_size * 0.2):
                        self.vel[i, 1] = 2
                    else:
                        self.vel[i, 1] = 1



    def _compute_position(self, args):
        """
        Position calculation of a particle

        Args:
        args: current position, current velocity, current number of unimproved iterations and current best objective

        Returs:
        New position, new velocity, new number of unimproved iterations and new best objective

        """
        x, vel, nIter, fx = args

        nIter_aux = 0
        reset_threshold = (self.max_steps / self.member_size) * (self.c1 / 1000)
        while nIter_aux <= vel[0]:
            if (nIter >= reset_threshold) and (np.random.rand() < vel[2]):
                x_parts = np.array_split(x, 4)
                x = np.concatenate([x_parts[1], x_parts[3], x_parts[0], x_parts[2]])
                fx = self._objective(x)
                nIter = 0

            if vel[1] == 1:
                for xn in self._two_opt_FLip(x):
                    nIter_aux += 1
                    nIter += 1
                    fn =  self._objective(xn)
                    if fx > fn:
                        x = xn
                        fx = fn
                        nIter = 0
                        break

                    if nIter_aux >= vel[0]:
                        break
            elif vel[1] == 2:
                for xn in self._two_and_a_half_opt(x):
                    nIter_aux += 1
                    nIter += 1
                    fn =  self._objective(xn)
                    if fx > fn:
                        x = xn
                        fx = fn
                        nIter = 0
                        break

                    if nIter_aux >= vel[0]:
                        break

            elif vel[1] == 3:
                for xn in self._two_opt(x):
                    nIter_aux += 1
                    nIter += 1
                    fn =  self._objective(xn)
                    if fx > fn:
                        x = xn
                        fx = fn
                        nIter = 0
                        break

                    if nIter_aux >= vel[0]:
                        break
            elif vel[1] == 4:
                for xn in self._k_opt_Flip(x,self.k):
                    nIter_aux += 1
                    nIter += 1
                    fn =  self._objective(xn)
                    if fx > fn:
                        x = xn
                        fx = fn
                        nIter = 0
                        break

                    if nIter_aux >= vel[0]:
                        break
            elif vel[1] == 5:
                for xn in self._k_opt_Random(x,self.k):
                    nIter_aux += 1
                    nIter += 1
                    fn =  self._objective(xn)
                    if fx > fn:
                        x = xn
                        fx = fn
                        nIter = 0
                        break

                    if nIter_aux >= vel[0]:
                        break

        return x, nIter, fx, vel

    
    def _two_opt_FLip(self, x: np.ndarray) -> Generator[np.ndarray, np.ndarray, None]:
        """
        2-opt Flip
        """
        n = len(x)
        if not self.ring_mode:
            node_init = 0
        else:
            node_init = 1
        
        i_range = np.arange(node_init, n-1)
        i_range_random = np.random.choice(i_range, len(i_range), replace=False)
        for i in i_range_random:
            j_range = np.arange(i + 1, n)
            j_range_random = np.random.choice(j_range, len(j_range), replace=False)
            for j in j_range_random:
                xn = np.concatenate((x[:i], np.flip(x[i:j]), x[j:]))
                yield xn    
                         
   
    def _two_opt(self, x: np.ndarray) -> Generator[np.ndarray, np.ndarray, None]:
        """
        2-opt
        """
        n = len(x)
        if not self.ring_mode:
            node_init = 0
        else:
            node_init = 1
        
        i_range = np.arange(node_init, n-1)
        i_range_random = np.random.choice(i_range, len(i_range), replace=False)
        for i in i_range_random:
            j_range = np.arange(i + 1, n)
            j_range_random = np.random.choice(j_range, len(j_range), replace=False)
            for j in j_range_random:
                xn = x.copy()
                xn[i] = x[j]
                xn[j] = x[i]
                yield xn                   

    def _k_opt_Flip(self, x: np.ndarray, k: int) -> Generator[np.ndarray, np.ndarray, None]:
        """
        k-opt FLip
        """
        n = len(x)
        if not self.ring_mode:
            node_init = 0
        else:
            node_init = 1
        
        arr = np.arange(node_init, n)
        i_range = np.random.choice(arr, len(arr), replace=False)

        for i in i_range:
            if i+k > n:
                aux1 = np.flip(x[:k+i-n])
                aux2 = np.flip((x[i:]))
                aux = np.concatenate((aux2, aux1))
                a = aux[:k+i-n]
                b = x[k+i-n:i]
                c = aux[k+i-n:]
                xn = np.concatenate((a, b,c))
                yield xn 
            else:
                xn = np.concatenate((x[:i], np.flip(x[i:i+k]), x[i+k:n]))
                yield xn 

 

                        
    def _two_and_a_half_opt(self, x: np.ndarray) -> Generator[np.ndarray, np.ndarray, None]:
        """
        2,5-opt
        """
        n = len(x)
        i_range = np.arange(0, n) 

        for i in np.random.permutation(i_range):
            j_range = np.arange(i + 1, n)
            for j in np.random.permutation(j_range):
                xn = np.concatenate((
                x[:i],
                x[i + 1:j + 1],
                x[i:i + 1],
                x[j + 1:]
                ))
                yield xn
                
    def _k_opt_Random(self, x: np.ndarray, k: int) -> Generator[np.ndarray, np.ndarray, None]:
        """
        k-opt Random
        """
        n = len(x)
        k = min(k, n)
        if not self.ring_mode:
            node_init = 0
        else:
            node_init = 1

        arr = np.arange(node_init, n)
        i_range = np.random.choice(arr, len(arr), replace=False)

        for i in i_range:
            if i + k > n:
                aux1 = x[:k + i - n]
                aux2 = x[i:]
                aux = np.concatenate((aux2, aux1))
                aux = np.random.permutation(aux)
                a = aux[:k + i - n]
                b = x[k + i - n:i]
                c = aux[k + i - n:]
                xn = np.concatenate((a, b, c))
                yield xn
            else:
                xn = np.concatenate((x[:i], np.flip(x[i:i + k]), x[i + k:n]))
                yield xn

