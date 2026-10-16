# -*- coding: utf-8 -*-
"""
Created on Fri May 26 17:37:31 2023

@author: Ivan Hernandez Muñoz

Algorithm based on Solid's ParticleSwarm (Python framework for gradient-free optimization)
"""

import numpy as np
from typing import Generator

from .pso_config import PSOConfig

class ParticleSwarm:
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

    # Optional writer supplied on the solver class (shared by its instances).
    # It must expose write(history, file_path). Never store it on the instance:
    # bound worker methods serialize the solver's instance state.
    result_writer = None

    # Optional presenter supplied on the class, never in serialized instance state.
    # Receives scalar values and preformatted route/result strings only.
    console_presenter = None

    # Zero-argument factory; the active executor stays local to run().
    particle_executor_factory = None
    
    def __init__(self, matrix, config: PSOConfig):
        """Initialize shared state, preserving validation and conversion order."""
        self.config = config
        N, c1 = config.N, config.c1
        distance_matrix = matrix
        if distance_matrix.shape[0] == distance_matrix.shape[1]:
            self.distance_matrix = distance_matrix
        else:
            raise ValueError('Distance matrix must be square')
        
        self.ring_mode = config.ring_mode

        self.resetThresholdDivisor = config.reset_threshold_divisor
        self.primaryOperatorShare = config.primary_operator_share
        self.progressWarmupMultiplier = config.progress_warmup_multiplier
        
        self._initialize_problem()

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
                      
        
    def _get_console_presenter(self):
        presenter = type(self).console_presenter
        if presenter is None:
            from ...presentation.console_presenter import ConsolePresenter
            presenter = ConsolePresenter()
        return presenter

    def __str__(self):
        step, result = self._dataToSave()
        return self._get_console_presenter().format_result(
            step, self._result_label, result, str(self.global_best[0]))

    def _initialize_problem(self):
        """Initialize specialized state before computing objective bounds."""
        pass

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
        raise NotImplementedError
    

    

        
    
        
    

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

                  
            
    def _min_distance(self):
        """
        Shared minimum-distance bound.
        """
        min_distance = 0
        for raw in self.distance_matrix:
            non_zero_values = [value for value in raw if value != 0]
            if non_zero_values:        
                min_distance += min(non_zero_values)
                
        return min_distance

    def _min_values(self):
        raise NotImplementedError
               

    def _max_distance(self):
        """
        Shared maximum-distance bound.
        """
        max_distance = 0
        for raw in self.distance_matrix:
            max_distance += max(raw)
            
        return max_distance

    def _max_values(self):
        raise NotImplementedError



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
        
        executor_factory = type(self).particle_executor_factory
        if executor_factory is None:
            from ...infrastructure.executors.particle_executor import ParticleExecutor
            executor_factory = ParticleExecutor
        with executor_factory() as p:
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

                self._best()
                self._global_best()

                if self.cur_steps > self.member_size * self.progressWarmupMultiplier:
                    if verbose:
                        self._get_console_presenter().present_result(str(self))
                    if excel:
                        output_list.append(self._dataToSave())

                aux_n_steps += 1

        if excel:
            writer = type(self).result_writer
            if writer is None:
                from ...infrastructure.writers.excel_result_writer import ExcelResultWriter
                writer = ExcelResultWriter()
            writer.write(output_list, file_path)

        presenter = self._get_console_presenter()
        presenter.present_completion()
        presenter.present_result(str(self))
        return self.global_best[0], self._objective(self.global_best[0])

    def _dataToSave(self):
        raise NotImplementedError

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
            if 1 <= optType <= 5:
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
                    if i < (self.swarm_size * self.primaryOperatorShare):
                        self.vel[i, 1] = 1
                    else:
                        self.vel[i, 1] = 2
            elif optType == 15:
                    if i < (self.swarm_size * self.primaryOperatorShare):
                        self.vel[i, 1] = 1
                    else:
                        self.vel[i, 1] = 5
            elif optType == 21:
                    if i < (self.swarm_size * self.primaryOperatorShare):
                        self.vel[i, 1] = 2
                    else:
                        self.vel[i, 1] = 1
            else:
                raise ValueError(f"Invalid optType: {optType}")



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
        reset_threshold = (self.max_steps / self.member_size) * (self.c1 / self.resetThresholdDivisor)
        while nIter_aux < vel[0]:
            if (nIter >= reset_threshold) and (np.random.rand() < vel[2]):
                # Reset operator: split the route into four parts and reorder them as [1, 3, 0, 2].
                x_parts = np.array_split(x, 4)
                x = np.concatenate([x_parts[1], x_parts[3], x_parts[0], x_parts[2]])
                fx = self._objective(x)
                nIter = 0

            previous_nIter_aux = nIter_aux
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

            if nIter_aux == previous_nIter_aux:
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
        k = min(k, n)
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

