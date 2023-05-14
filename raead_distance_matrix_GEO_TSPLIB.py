# -*- coding: utf-8 -*-
"""
Created on Sat May 13 19:40:55 2023

@author: ihm12
"""
import numpy as np


def raead_distance_matrix_GEO_TSPLIB (archivo):
    
    # Abrir el archivo txt en modo de lectura
    with open(archivo, "r") as f:
        # Leer las líneas del archivo y almacenarlas en una lista
        lines = f.readlines()

    # Encontrar la línea que contiene la palabra clave "DIMENSION" y extraer el valor del número
    dimension_line = [line for line in lines if "DIMENSION" in line][0]
    dimension = int(dimension_line.split(":")[1])
    
    # Tipo de matriz en fichero
    formato_line = [line for line in lines if "EDGE_WEIGHT_FORMAT" in line][0]
    formato = str(formato_line.split(":")[1]).strip()
    

    # Encontrar la línea que contiene la palabra clave "EDGE_WEIGHT_SECTION" y a partir de esa línea, leer el resto de las líneas que contienen las coordenadas de los nodos
    node_coord_section_line = [line for line in lines if "EDGE_WEIGHT_SECTION" in line][0]
    node_coord_section_index = lines.index(node_coord_section_line) + 1
    node_coord_section_lines = lines[node_coord_section_index:node_coord_section_index + dimension]

    # Crear una matriz con el número "DIMENSION" de filas y columnas 
    #cities = [[0 for j in range(dimension)] for i in range(dimension)]
    distance_matrix = np.zeros((dimension,dimension))
    
    if formato == "FULL_MATRIX":
        # Rellenar la matriz
        for i, line in enumerate(node_coord_section_lines):
            parts = line.split()
            for j, part in enumerate(parts):
                distance_matrix[i][j] = int(part)
    elif formato == "UPPER_ROW":
        # Rellenar la matriz
        for i, line in enumerate(node_coord_section_lines):
            parts = line.split()
            for j in range(dimension):                         
                if (i == j):
                    distance_matrix[i][j] = 0
                elif (i > j):
                    distance_matrix[i][j] = distance_matrix[j][i]
                else:
                    distance_matrix[i][j] = int(parts[j-i-1])
            
  
    return distance_matrix