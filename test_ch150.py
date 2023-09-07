# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
from Read_TSPLIB.raead_distance_matrix_EUC2D_TSPLIB import raead_distance_matrix_EUC2D_TSPLIB
from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess
import numpy as np


distance_matrix = raead_distance_matrix_EUC2D_TSPLIB("./DataSets/ch150.tsp")
arr_rounded = np.round(distance_matrix, decimals=0)

"""RING MODE"""

N = 8
c1 = 8000
optType = 10
algorithm = ParticleSwarm_VarOptMultiprocess(N,c1,arr_rounded,True) #6528
algorithm.run(True, optType, False, " ", True, 0.2, 0.8)
