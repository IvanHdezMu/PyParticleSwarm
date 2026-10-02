# -*- coding: utf-8 -*-
"""
Created on Sat May 13 19:40:55 2023

@author: ihm12
"""
import numpy as np


def read_distance_matrix_EUC2D_TSPLIB(file_path):
    
    # Open the text file for reading
    with open(file_path, "r") as f:
        # Read all lines into a list
        lines = f.readlines()

    # Find DIMENSION and extract its numeric value
    dimension_line = [line for line in lines if "DIMENSION" in line][0]
    dimension = int(dimension_line.split(":")[1])

    # Read the node coordinates following NODE_COORD_SECTION
    node_coord_section_line = [line for line in lines if "NODE_COORD_SECTION" in line][0]
    node_coord_section_index = lines.index(node_coord_section_line) + 1
    node_coord_section_lines = lines[node_coord_section_index:node_coord_section_index + dimension]

    # Create a matrix with DIMENSION rows and three columns
    cities = [[0 for j in range(3)] for i in range(dimension)]

    # Fill the matrix
    for line in node_coord_section_lines:
        parts = line.split()
        node = float(parts[0]) - 1.0
        x = float(parts[1])
        y = float(parts[2])
        cities[int(node)][0] = int(node)
        cities[int(node)][1] = int(x)
        cities[int(node)][2] = int(y)
        
        
        
    N = len(cities)  # Number of cities
    # Distance matrix
    distance_matrix = np.zeros((N, N))
    for i, start in enumerate(cities):
        for j, end in enumerate(cities):
            x1 = start[1]
            y1 = start[2]
            x2 = end[1]
            y2 = end[2]
            distance_matrix[i][j] =((x2 - x1)**2 + (y2 - y1)**2)**0.5
            
    return distance_matrix
