# -*- coding: utf-8 -*-
"""
Created on Sat May 13 19:40:55 2023

@author: ihm12
"""
import numpy as np


def read_geo_matrix(file_path):
    
    # Open the text file for reading
    with open(file_path, "r") as f:
        # Read all lines into a list
        lines = f.readlines()

    # Find DIMENSION and extract its numeric value
    dimension_line = [line for line in lines if "DIMENSION" in line][0]
    dimension = int(dimension_line.split(":")[1])
    
    # Matrix format in the file
    matrix_format_line = [line for line in lines if "EDGE_WEIGHT_FORMAT" in line][0]
    matrix_format = str(matrix_format_line.split(":")[1]).strip()
    

    # Read the weights following EDGE_WEIGHT_SECTION
    node_coord_section_line = [line for line in lines if "EDGE_WEIGHT_SECTION" in line][0]
    node_coord_section_index = lines.index(node_coord_section_line) + 1
    node_coord_section_lines = lines[node_coord_section_index:node_coord_section_index + dimension]

    # Create a square matrix with DIMENSION rows and columns 
    #cities = [[0 for j in range(dimension)] for i in range(dimension)]
    distance_matrix = np.zeros((dimension,dimension))
    
    if matrix_format == "FULL_MATRIX":
        # Fill the matrix
        for i, line in enumerate(node_coord_section_lines):
            parts = line.split()
            for j, part in enumerate(parts):
                distance_matrix[i][j] = int(part)
    elif matrix_format == "UPPER_ROW":
        # Fill the matrix
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
