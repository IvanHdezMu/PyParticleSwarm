from abc import ABCMeta, abstractmethod
from random import random
from numpy import apply_along_axis, argmin, array, copy, diag_indices_from, dot, zeros
from numpy.random import uniform

import numpy as np
from typing import Generator, List

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
    scores = None
    best = None
    global_best = None

    c1 = None
    c2 = None
    c3 = None

    cur_steps = None
    max_steps = None
    min_objective = None

    def __init__(self, swarm_size, lower_bound, upper_bound, c1, c2, c3,
                 max_steps,distance_matrix, min_objective=None):
        """

        :param swarm_size: number of members in swarm

        :param lower_bound: list of lower bounds, where ith element is ith lower bound
        :param upper_bound: list of upper bounds, where ith element is ith upper bound
        :param c1: constant for 1st term in velocity calculation
        :param c2: contsant for 2nd term in velocity calculation
        :param c3: constant for 3rd term in velocity calculation
        :param max_steps: maximum steps to run algorithm for
        :param distance_matrix: distance matrix between nodes
        :param min_objective: objective function value to stop algorithm once reached
        """
        self.borrame_i = 0
        self.borrame_fx = 0
        
        self.distance_matrix = distance_matrix
        self.sum_min_raws()
        self.sum_max_raws()
        self.member_size = distance_matrix.shape[0]
        
        if isinstance(swarm_size, int) and swarm_size > 0:
            self.swarm_size = swarm_size
        else:
            raise ValueError('Swarm size must be a positive integer')


        if all([isinstance(x, (int, float)) for x in lower_bound]):
            self.lower_bound = array([float(x) for x in lower_bound])
        else:
            raise ValueError('Lower bounds must be numeric types')

        if all([isinstance(x, (int, float)) for x in upper_bound]):
            self.upper_bound = array([float(x) for x in upper_bound])
        else:
            raise ValueError('Upper bounds must be numeric types')

        aux = []
        for i in range(self.swarm_size):
            aux.append(np.random.choice(self.member_size,self.member_size,replace=False))
            
        self.pos = np.array(aux)

        self.vel = uniform(self.lower_bound - self.upper_bound, self.upper_bound - self.lower_bound,
                           size=(swarm_size, self.member_size))

        self.best = copy(self.pos)

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

        if min_objective is not None:
            if isinstance(min_objective, (int, float)):
                self.min_objective = float(min_objective)
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
        self.vel = uniform(self.lower_bound - self.upper_bound, self.upper_bound - self.lower_bound,
                           size=(self.swarm_size, self.member_size))
        self.scores = self._score(self.pos)
        self.best = copy(self.pos)
        self.cur_steps = 0
        self._global_best()

    @abstractmethod
    def _objective(self, member):
        """
        Returns objective function value for a member of swarm -
        operates on 1D numpy array

        :param member: a member
        :return: objective function value of member
        """
        total_distance = 0
        for i in range(len(member)-1):
            current_node = member[i]
            next_node = member[i+1]
            # Sum of the distance to the next node
            total_distance += self.distance_matrix[current_node, next_node]
             
        return abs(self.min_distance-total_distance)

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
        self.best = array(best)

    def _global_best(self):
        """
        Finds the global best across swarm

        :return: None
        """
        if self.global_best is None or min(self.scores) < self._objective(self.global_best[0]):
            self.global_best = array([self.pos[argmin(self.scores)]] * self.swarm_size)

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

            u1 = zeros((self.swarm_size, self.swarm_size))
            u1[diag_indices_from(u1)] = [random() for x in range(self.swarm_size)]
            u2 = zeros((self.swarm_size, self.swarm_size))
            u2[diag_indices_from(u2)] = [random() for x in range(self.swarm_size)]

            vel_new = (self.c1 * self.vel) + \
                      (self.c2 * dot(u1, (self.best - self.pos))) + \
                      (self.c3 * dot(u2, (self.global_best - self.pos)))

            pos_new = self._compute_position(vel_new) #self.pos + vel_new

            self._best(self.pos, pos_new)
            self.pos = pos_new
            self.scores = self._score(self.pos)
            self._global_best()

            if self._objective(self.global_best[0]) < (self.min_objective or 0):
                print("TERMINATING - REACHED MINIMUM OBJECTIVE")
                return self.global_best[0], self._objective(self.global_best[0])
        print("TERMINATING - REACHED MAXIMUM STEPS")
        return self.global_best[0], self._objective(self.global_best[0])

    def _compute_position(self, vel_new):
        """Update the position of the swarm
        This computes the next position in a discrete swarm.
        """
        
        x = self.pos 
        n_particles = x.shape[0]  # number of particles
        
        fx = []
        for i in range(n_particles-1):
            self.borrame_i = i
            self.borrame_fx = fx
            fx.append(self._objective(x[i])) 
                   
        """k_inner_max = 10 * len(x)
                
        for i in range(n_particles-1):
            for k in range(k_inner_max):
                xn = next (self._two_opt_gen(x[i].tolist()))
                fn =  self._objective(xn)     
                

                if self._acceptance_rule(fx[i], fn, np.mean(vel_new[i])):
                    x[i], fx[i] = xn, fn
                    break"""  
                    
        for i in range(n_particles-1):

            xn = next (self._two_opt_gen(x[i].tolist()))
            fn =  self._objective(xn)              

            if self._acceptance_rule(fx[i], fn, np.mean(vel_new[i])):
                x[i], fx[i] = xn, fn                
                    
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
        """Metropolis acceptance rule"""
    
        dfx = fn - fx
        if (dfx < 0):
            return True
        elif (dfx > 0) and (np.random.rand() <= np.exp(-(fn - fx) / velocity)):
            return True
        else:
            return False
    
    def sum_min_raws(self):
        self.min_distance = 0
        for raw in self.distance_matrix:
            non_zero_values = [value for value in raw if value != 0]
            if non_zero_values:
                self.min_distance += min(non_zero_values)


    def sum_max_raws(self):
        self.max_distance = 0
        for raw in self.distance_matrix:
            self.max_distance += max(raw)
