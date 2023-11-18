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

list_c1 = [6000, 7000, 8000, 9000, 10000]
list_minRandom = [0.2]
list_maxRandom = [0.8]

random = True
kv = 10
optType = 10
N = 8

for c1 in list_c1:
    algorithm = ParticleSwarm_VarOptMultiprocess(N, c1, arr_rounded, True)  # xxx6528
    for minRandom in list_minRandom:
        for maxRandom in list_maxRandom:
            for number in range(1, 11):
                pathExcel = ("Resultados/ch150_" + str(random) + "_" + str(N) + "_" + str(c1) + "_" +
                             str(optType) + '_' + str(kv) + "_" + str(minRandom) + "_" + str(maxRandom) +
                             "_" + str(number) + ".xlsx")
                algorithm.run(False, optType, True, pathExcel, True, minRandom, maxRandom)
