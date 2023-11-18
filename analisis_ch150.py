# -*- coding: utf-8 -*-
"""
Created on Fri May 12 19:35:57 2023

@author: ihm12
"""

# Import modules
import pandas as pd

list_c1 = [6000, 7000, 8000, 9000, 10000]
list_minRandom = [0.2]
list_maxRandom = [0.8]

random = True
kv = 10
optType = 10
list_N = [8, 10]

# Lista para almacenar los Datos
tabla = pd.DataFrame(columns=['random', 'N', 'c1','optType', 'kv', 'minR', 'maxR', 'media_valor_min', 'media_step_valor_minimo', 'mejor_resultado'])


for N in list_N:
    for c1 in list_c1:
        for minRandom in list_minRandom:
            for maxRandom in list_maxRandom:
                valor_min = []
                step_valor_min = []
                media_valor_min = 0
                media_step_valor_minimo = 0
                for number in range(1, 11):
                    pathExcel = ("Resultados/analisis_9/ch150_" + str(random) + "_" + str(N) + "_" + str(c1) + "_" +
                                 str(optType) + '_' + str(kv) + "_" + str(minRandom) + "_" + str(maxRandom) +
                                 "_" + str(number) + ".xlsx")
                    df = pd.read_excel(pathExcel)  # Cargar el archivo Excel y crear el DataFrame

                    # Obtener el valor mínimo de la columna "Resultado"
                    valor_min.append(df['Resultado'].min())

                    # Obtener el valor de la columna "Step" en la fila correspondiente al índice mínimo
                    indice_minimo = df['Resultado'].idxmin()
                    step_valor_min.append(df.loc[indice_minimo, 'Step'])

                media_valor_min = sum(valor_min) / len(valor_min)
                media_step_valor_minimo = sum(step_valor_min) / len(step_valor_min)
                mejor_resultado = min(valor_min)

                fila = pd.Series((random, N, c1, optType, kv, minRandom, maxRandom, media_valor_min, media_step_valor_minimo, mejor_resultado),
                                 index=tabla.columns)
                tabla = tabla._append(fila, ignore_index=True)

                tabla.to_excel('Resultados/Analisis_ch150.xlsx', index=False)


print(tabla)
