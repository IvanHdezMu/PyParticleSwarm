# -*- coding: utf-8 -*-
"""
Created on Sat May 13 19:40:55 2023

@author: ihm12
"""
import numpy as np


def raead_distance_matrix_COORD_GEO_TSPLIB (archivo):
    
    # Abrir el archivo txt en modo de lectura
    with open(archivo, "r") as f:
        # Leer las líneas del archivo y almacenarlas en una lista
        lines = f.readlines()

    # Encontrar la línea que contiene la palabra clave "DIMENSION" y extraer el valor del número
    dimension_line = [line for line in lines if "DIMENSION" in line][0]
    dimension = int(dimension_line.split(":")[1])

    # Encontrar la línea que contiene la palabra clave "NODE_COORD_SECTION" y a partir de esa línea, leer el resto de las líneas que contienen las coordenadas de los nodos
    node_coord_section_line = [line for line in lines if "NODE_COORD_SECTION" in line][0]
    node_coord_section_index = lines.index(node_coord_section_line) + 1
    node_coord_section_lines = lines[node_coord_section_index:node_coord_section_index + dimension]

    # Crear una matriz con el número de filas "DIMENSION" y 3 columnas
    cities = [[0 for j in range(3)] for i in range(dimension)]

    PI = 3.141592;
    # Rellenar la matriz
    for line in node_coord_section_lines:
        parts = line.split()
        node = int(parts[0]) - 1
        x = float(parts[1])
        y = float(parts[2])   
        deg = np.round(x);
        min = x - deg
        latitude = PI * (deg + 5.0 * min / 3.0 ) / 180.0
        deg = np.round(y)
        min = y - deg
        longitude = PI * (deg + 5.0 * min / 3.0 ) / 180.0
        cities[node][0] = node
        cities[node][1] = latitude
        cities[node][2] = longitude
        
        
        
    N = len(cities) # Numero de ciudades
    

    RRR = 6378.388;
    #Matriz con distancias
    distance_matrix = np.zeros((N, N))
    for i, start in enumerate(cities):
        for j, end in enumerate(cities):  
            q1 = np.cos( start[2] - end[2] ) #cos(longitude1 - longitude2)
            q2 = np.cos( start[1] - end[1] ) #cos(latitude1 - latitude2)
            q3 = np.cos( start[1] + end[1] ) #cos(latitude1 + latitude2)
            distance_matrix[i][j] = (int) ( RRR * np.arccos( 0.5*((1.0+q1)*q2 - (1.0-q1)*q3) ) + 1.0)
            
    return distance_matrix

 