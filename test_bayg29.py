# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
from raead_distance_matrix_GEO_TSPLIB import raead_distance_matrix_GEO_TSPLIB
from ParticleSwarm_TwoOpt import ParticleSwarm_TwoOpt


distance_matrix = raead_distance_matrix_GEO_TSPLIB("bayg29.tsp")

"""RING MODE"""
#Ualgorithm = ParticleSwarm_TwoOpt(50, 0.1, 0.6, 0.2, 100, distance_matrix,True) #1620/1618/1610/1615
algorithm = ParticleSwarm_TwoOpt(50, 0.1, 0.6, 0.3, 100, distance_matrix,True) #1610/1610/1615/1610
algorithm.run()
    

