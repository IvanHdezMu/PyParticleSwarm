# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
from Read_TSPLIB.raead_distance_matrix_GEO_TSPLIB import raead_distance_matrix_GEO_TSPLIB
from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess
import numpy as np



distance_matrix = raead_distance_matrix_GEO_TSPLIB("./DataSets/bays29.tsp")

"""RING MODE"""

N = 8
c1 = 1000

algorithm = ParticleSwarm_VarOptMultiprocess(N,c1,distance_matrix,True)
algorithm.run(False, 10,False, " ", True)

print(algorithm.nIter)