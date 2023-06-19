# -*- coding: utf-8 -*-
"""
Created on Sat May 13 19:40:55 2023

@author: ihm12
"""
import numpy as np


def raead_distance_matrix_ATT_TSPLIB (archivo):
    
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

    # Rellenar la matriz
    for line in node_coord_section_lines:
        parts = line.split()
        node = float(parts[0]) - 1.0
        x = float(parts[1])
        y = float(parts[2])
        cities[int(node)][0] = int(node)
        cities[int(node)][1] = int(x)
        cities[int(node)][2] = int(y)
        
        
        
    N = len(cities) # Numero de ciudades
    #Matriz con distancias
    distance_matrix = np.zeros((N, N))
    for i, start in enumerate(cities):
        for j, end in enumerate(cities):
            x1 = start[1]
            y1 = start[2]
            x2 = end[1]
            y2 = end[2]
            xd = x1 - x2
            yd = y1 - y2
            rij = np.sqrt( (xd*xd + yd*yd) / 10.0 )
            tij = np.round(rij)
            if (tij < rij):
                distance_matrix[i][j] = tij + 1
            else:
                distance_matrix[i][j] = tij

            
    return distance_matrix