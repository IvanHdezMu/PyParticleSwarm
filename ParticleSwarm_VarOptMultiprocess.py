# -*- coding: utf-8 -*-
"""
Created on Fri May 26 17:37:31 2023

@author: ihm12
"""

import numpy as np
from typing import Generator
from multiprocessing import Pool
import pandas as pd

class ParticleSwarm_VarOptMultiprocess:
    
    swarm_size = None
    member_size = None
    #lower_bound = None
    #upper_bound = None

    pos = None
    scores = None
    best = None
    global_best = None
    
    fx = None
    f_best = None
    f_global_best = None
    
    vel = None
    nIter = None

    N = None
    c1 = None
    #c2 = None
    #c3 = None

    cur_steps = None
    
    def __init__(self, N, c1, distance_matrix, ring_mode=False, refuel_mode=False,
                 prices=None, maxCapacity=None, consumption=None):
        """
        N = Number of particles
        C1 x Number of nodes = max steps
        distance_matrix = distance between nodes
        ring_mode = add distance from the last node to the first node
        refuel_mode = false->TSP mode active; true->TSPWR mode active
        prices = array with refueling prices
        maxCapacity = vehicle capacity in liters
        consumption = consumption of the vehicle in Km per liter
        """
        
        if distance_matrix.shape[0] == distance_matrix.shape[1]:
            self.distance_matrix = distance_matrix
        else:
            raise ValueError('Distance matrix must be square')
        
        self.ring_mode = ring_mode
        
        self.refuel_mode = refuel_mode
        if refuel_mode == True: 
            
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

        if isinstance(c1, (int, float)):
            self.c1 = int(c1)
        
        self.min_value = self._min_values()
        self.max_value = self._max_values()
            
        self.member_size = distance_matrix.shape[0]

        self.swarm_size = N
        
        # max_steps
        self.max_steps = self.c1 * self.member_size
                      
        
    def __str__(self):
        if self.refuel_mode == False:
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
        return self.__str__()        
        
    def _clear(self, randomReset, minRandom, maxRandom):
        """
        Resets the variables that are altered on a per-run basis of the algorithm
        
        :return: None
        """
        
        aux = []
        for i in range(self.swarm_size):
            aux.append(np.random.choice(self.member_size,self.member_size,replace=False))
        self.pos = np.array(aux) 
            
        self.fx = self._score(self.pos)   
        self.nIter = np.zeros(self.member_size)

        vel0 = (np.ones(self.swarm_size) * (self.member_size * 1)).astype(int)
        vel1 = np.ones(self.swarm_size)
        if randomReset:
            aux_vel2 = np.arange(1, self.swarm_size + 1)
            vel2 = np.interp(aux_vel2, [0, self.swarm_size], [minRandom, maxRandom])  # Random probability
        else:
            vel2 = np.zeros(self.swarm_size)
        self.vel = np.column_stack((vel0, vel1, vel2))

        self.scores = self._score(self.pos)
        self.best = np.copy(self.pos)
        
        self.global_best = self.best # only because of the size
        self.f_global_best = np.ones(self.member_size) * self.max_value
        self.f_best = self._score(self.best)
        
        self.cur_steps = 1
        self._global_best()
            
     
    def _objective(self, member):
        if self.refuel_mode == False:
            return self._objectiveTSP(member)
        else:
            return self._objectiveTSPWR(member)
    
    def _objectiveTSP(self, member):
        return abs(self.min_value-self._calculate_distance(member))
    
    def _calculate_distance(self, member):
        total_distance = 0
        
        for i in range(len(member)-1): # no travel from last node
            current_node = member[i]
            next_node = member[i+1]
            # Sum of the distance to the next node
            total_distance += self.distance_matrix[current_node, next_node]
        if self.ring_mode == True:
            total_distance += self.distance_matrix[next_node, member[0]]
            
        return total_distance
        
    
        
    def _objectiveTSPWR(self, member):
        return abs(self.min_value-self._calculate_refuel(member)) 
    
    def _calculate_refuel(self, member):
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
        Where the target is better it is added to best
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
            self.vel[:][1] = self.vel[ordered_indexes][1]
            
            min_index = np.argmin(self.f_best)    
            if self.f_best[min_index] < self.f_global_best[0]:
                self.f_global_best[0:] = self.f_best[min_index]
                self.global_best[0:] = self.best[min_index]

                  
            
    def _min_values(self):
        """
        Minimum distance calculation
        Minimum price calculation
        """
        min_distance = 0
        for raw in self.distance_matrix:
            non_zero_values = [value for value in raw if value != 0]
            if non_zero_values:        
                min_distance += min(non_zero_values)
                
        if self.refuel_mode == False:
            return min_distance
        else:
            sorted_prices = np.sort(self.prices)
            return self._calculate_path_cost(min_distance, sorted_prices)
               

    def _max_values(self):
        """
        Maximun distance calculation
        Maximun price calculation
        """        
        max_distance = 0
        for raw in self.distance_matrix:
            max_distance += max(raw)
            
        if self.refuel_mode == False:
            return max_distance
        else:
            reverse_sorted_prices = np.sort(self.prices)[::-1]
            return self._calculate_path_cost(max_distance,
                                             reverse_sorted_prices)

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

    def _path_prices(self, path):  # array of prices of the path
        prices_arr = np.zeros(len(path))
        for i in range(len(path)):
            prices_arr[i] = self.prices[path[i]]
        return prices_arr

    def run(self, verbose=True, optType=1, excel=True, file_path = 'output_file.xlsx', randomReset=True, minRandom=0.2, maxRandom=0.8):
        """
        Conducts particle swarm optimization

        :param verbose: indicates whether or not to print progress regularly
        :param excel: indicates whether or not to save progress regularly
        :return: best member of swarm and objective function value of best member of swarm
        """
        self._clear(randomReset, minRandom, maxRandom)
        
        output_list = []

        aux_n_steps = 1
        while self.cur_steps <= self.max_steps:

            self.vel[:,0] = (np.ones(self.swarm_size) * (self.member_size * aux_n_steps)).astype(int)
            self._Opt_Type(optType) #self.vel[:][1]= ...  #Type of opt
            #self.vel[:][2] =... #Random probability

            #self.pos, self.nIter, self.fx = self._compute_position(self.pos, self.vel, self.nIter, self.fx)
            with Pool() as p:
                results = p.map(self._compute_position, zip(self.pos, self.vel, self.nIter, self.fx))
            p.close()
            p.join()

            pos, nIter, fx, vel = zip(*results)
            self.pos = np.array(pos)
            self.nIter = np.array(nIter)
            self.fx = np.array(fx)
            self.vel = np.array(vel)

            self.cur_steps += self.vel[0][0]

            if self.cur_steps > self.member_size * 5:
                if verbose:
                    print(self)
                if excel:
                    output_list.append(self._dataSave())

            aux_n_steps += 1

            self._best()
            self.scores = self._score(self.pos)
            self._global_best()

        if excel:
            columnas = ['Step', 'Resultado']
            df = pd.DataFrame(output_list, columns=columnas)
            df.to_excel(file_path, index=False)

        print("TERMINATING - REACHED MAXIMUM STEPS")
        print(self)
        return self.global_best[0], self._objective(self.global_best[0])

    def _dataSave(self):
        if self.refuel_mode == False:
            return [self.cur_steps, self._calculate_distance(self.global_best[0])]
        else:
            return [self.cur_steps, self._calculate_refuel(self.global_best[0])]

    def _Opt_Type(self, optType):
        """
        1 = 2-Opt con Flip
        2 = 2,5-Opt
        3 = 2-Opt
        4 = v-Opt
        5 = k-Opt
        """
        '''for i, nIter in enumerate(self.nIter):
            if nIter > (self.max_steps / self.member_size):
                if self.vel[i][1] == 1:
                    self.vel[i][1] = 2
                else:
                    self.vel[i][1] = 1'''

        for i, nIter in enumerate(self.nIter):
            self.vel[i][1] == optType


    def _compute_position(self, args):
        """Update the position of the swarm
        This computes the next position in a discrete swarm.
        """
        x, vel, nIter, fx = args

        nIter_aux = 0
        while nIter_aux <= vel[0]:
            if (nIter >= (self.max_steps / self.member_size) * (self.c1/1000)) and (np.random.rand() < vel[2]):
                x_parts = np.array_split(x, 4)
                x = np.concatenate([x_parts[1], x_parts[3], x_parts[0], x_parts[2]])
                fx = self._objective(x)
                nIter = 0

            if vel[1] == 1:
                for j, xn in enumerate(self._two_opt_FLip(x)):
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
                for j, xn in enumerate(self._two_and_a_half_opt(x)):
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
                for j, xn in enumerate(self._two_opt(x)):
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
                for j, xn in enumerate(self._v_opt_gen(x,10)):
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
                for j, xn in enumerate(self._k_opt_gen(x,10)):
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
        """2-opt Flip"""
        n = len(x)
        if self.ring_mode == False:
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
                xn = np.concatenate((xn[:i], np.flip(xn[i:j]), xn[j:]))
                yield xn    
                         
   
    def _two_opt(self, x: np.ndarray) -> Generator[np.ndarray, np.ndarray, None]:
        """2-opt"""
        n = len(x)
        if self.ring_mode == False:
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

    def _v_opt_gen(self, x: np.ndarray, k: int) -> Generator[np.ndarray, np.ndarray, None]:
        """v-opt FLip"""
        n = len(x)
        if self.ring_mode == False:
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
        """2h-opt"""
        n = len(x)
        i_range = np.arange(0, n) 

        for i in np.random.permutation(i_range):
            j_range = np.arange(i + 1, n)
            for j in np.random.permutation(j_range):
                xn = np.copy(x)
                node = xn[i]
                xn = np.delete(xn, i)
                xn = np.insert(xn, j, node)
                yield xn
                
    def _k_opt_gen(self, x: np.ndarray, k: int) -> Generator[np.ndarray, np.ndarray, None]:
        """k-opt Random"""
        n = len(x)
        if self.ring_mode == False:
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

