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

list_random = [True]
list_N = [2, 4, 6, 8, 10, 12, 14, 16]
list_c1 = [2000]
optType = 10

for i, random in enumerate(list_random):
    for j, N in enumerate(list_N):
        for k, c1 in enumerate(list_c1):
            algorithm = ParticleSwarm_VarOptMultiprocess(N, c1, distance_matrix, True) #2020.000000
            for number in range(1, 11):
                pathExcel = "Resultados/bays29_" + str(random) + "_" + str(N) + "_" + str(c1) + "_" + str(optType) + "_" + str(number) + ".xlsx"
                algorithm.run(False, optType, True, pathExcel, random)

