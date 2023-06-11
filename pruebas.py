# -*- coding: utf-8 -*-
"""
Created on Fri May 26 18:26:40 2023

@author: ihm12
"""


# Import modules
import numpy as np
import pandas as pd
from geopy import distance

from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess

#constant data
maxCapacity = 150.0 # capacidad del vehiculo en litros
consumption = 7.0 # consumo del vehiculo en Km por litro

# leer los datos del archivo Excel y almacenarlos en un DataFrame
df = pd.read_excel('ciudades_Bahia30D.xlsx')


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
        

"NO RING MODE"        
 
c1 = 1.4#1.5
algorithm = ParticleSwarm_VarOptMultiprocess(c1,distance_matrix,False)
algorithm.run(True)