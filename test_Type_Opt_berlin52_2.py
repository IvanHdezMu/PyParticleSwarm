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


minRandom = 0.2
maxRandom = 0.8
kv=10

random = True
list_c1 = [2000, 2200, 2400, 2600, 2800, 3000] #
list_optType = [21] #optType = 10
N = 8

for c1 in list_c1:
    for optType in list_optType:
        algorithm = ParticleSwarm_VarOptMultiprocess(N, c1, arr_rounded, True)  # 7542.00
        for number in range(1, 31):
            pathExcel = ("Resultados/berlin52_" + str(random) + "_" + str(N) + "_" + str(c1) + "_" +
                         str(optType) + '_' + str(kv) + "_" + str(minRandom) + "_" + str(maxRandom) +
                         "_" + str(number) + ".xlsx")
            algorithm.run(False, optType, True, pathExcel, True, minRandom, maxRandom)
