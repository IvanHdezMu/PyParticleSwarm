# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
import pandas as pd

# Lista para almacenar los DataFrames
dataframes = []


for optType in range(1, 6):
    valor_min = []
    step_valor_min = []
    media_valor_min = 0
    media_step_valor_minimo = 0
    for number in range(1, 11):
        pathExcel = "Resultados/00/berlin52_" + str(optType) + "_" + str(number) + ".xlsx"
        df = pd.read_excel(pathExcel)  # Cargar el archivo Excel y crear el DataFrame
        dataframes.append(df)

        # Obtener el valor mínimo de la columna "Resultado"
        valor_min.append(df['Resultado'].min())

        # Obtener el valor de la columna "Step" en la fila correspondiente al índice mínimo
        indice_minimo = df['Resultado'].idxmin()
        step_valor_min.append(df.loc[indice_minimo, 'Step'])

    media_valor_min = sum(valor_min) / len(valor_min)
    media_step_valor_minimo = sum(step_valor_min) / len(step_valor_min)

    print("Tipo %d", optType)
    print("Valores mínimos:", valor_min)
    print("Media Valores mínimos:", media_valor_min)
    print("Steps Valores mínimos", media_step_valor_minimo)
    print("Media Steps Valores mínimos:", media_step_valor_minimo)

print(len(dataframes))


