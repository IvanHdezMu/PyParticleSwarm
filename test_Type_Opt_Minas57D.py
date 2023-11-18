# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
from Read_TSPLIB.raead_distance_matrix_GEO_TSPLIB import raead_distance_matrix_GEO_TSPLIB
from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess
import numpy as np
import pandas as pd
from geopy import distance

#constant data
maxCapacity = 150.0 # capacidad del vehiculo en litros
consumption = 7.0 # consumo del vehiculo en Km por litro

# leer los datos del archivo Excel y almacenarlos en un DataFrame
df = pd.read_excel('./DataSets/Minas57D.xlsx')

cities = []
# recorrer el DataFrame y agregar cada fila como una tupla a la lista de ciudades
for index, row in df.iterrows():
    city = index
    lat = row[1]
    long = row[2]
    C = row[3]
    cities.append((city, lat, long, C))

prices = df.iloc[:, 3].values

N = len(cities) # Numero de ciudades
#Matriz con distancias
distance_matrix = np.zeros((N, N))
for i, start in enumerate(cities):
    for j, end in enumerate(cities):
        coord1 = (start[1], start[2]) # coordenadas de latitud y longitud del primer punto
        coord2 = (end[1], end[2]) # coordenadas de latitud y longitud del segundo punto
        distance_matrix[i][j] = distance.distance(coord1, coord2).km # distancia entre los dos puntos en Km



random = True
N = 8
c1 = 3000
optType = 10
list_Ring = [False, True]
list_Full = [False, True]

for i, ring in enumerate(list_Ring):
    for j, full in enumerate(list_Full):
        algorithm = ParticleSwarm_VarOptMultiprocess(N, c1, distance_matrix, ring, True, prices, maxCapacity,
                               consumption, full)
        for number in range(1, 31):
            pathExcel = "Resultados/Minas57D_" + str(random) + "_" + str(N) + "_" + str(c1) + "_" + str(optType) + "_" + str(ring) + "_" + str(full) + "_" + str(number) + ".xlsx"
            algorithm.run(False, optType, True, pathExcel, random)

