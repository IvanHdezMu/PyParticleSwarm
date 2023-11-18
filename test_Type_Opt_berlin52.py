# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
from Read_TSPLIB.raead_distance_matrix_EUC2D_TSPLIB import raead_distance_matrix_EUC2D_TSPLIB
from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess
import numpy as np


distance_matrix = raead_distance_matrix_EUC2D_TSPLIB("./DataSets/berlin52.tsp")
arr_rounded = np.round(distance_matrix, decimals=0)

"""RING MODE"""

list_random = [True]
list_N = [8]
list_c1 = [1000, 2000, 5000]
list_optType = [10]
list_kv = [10]
list_minRandom = [0.0, 0.2, 0.4]
list_maxRandom = [0.4, 0.6, 0.8]

for i, random in enumerate(list_random):
    for j, N in enumerate(list_N):
        for k, c1 in enumerate(list_c1):
            algorithm = ParticleSwarm_VarOptMultiprocess(N, c1, arr_rounded, True)  # 7542.00
            for n, optType in enumerate(list_optType):
                for m, kv in enumerate(list_kv):
                    for minRandom in enumerate(list_minRandom):
                        for maxRandom in enumerate(list_maxRandom):
                            for number in range(1, 11):
                                pathExcel = "Resultados/berlin52_"+ str(random) + "_" + str(N) + "_" + str(c1) + "_" + str(optType) +  "_" + str(kv) + "_" + str(number) + "_" + str(minRandom) + "_" + str(maxRandom) + ".xlsx"
                                algorithm.run(False, optType, True, pathExcel, random, minRandom, maxRandom, kv, kv)

