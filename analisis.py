"""Shared engine for the analyses defined in analysis_options.json."""
from itertools import product
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
METRICS = ['media_valor_min', 'media_step_valor_minimo', 'mejor_resultado']


def load_analysis_options(path=None):
    with Path(path or ROOT / 'analysis_options.json').open(encoding='utf-8') as stream:
        analyses = json.load(stream)['analyses']
    identifiers = set()
    for analysis in analyses:
        if analysis['id'] in identifiers:
            raise ValueError(f"Identificador de análisis duplicado: {analysis['id']}")
        identifiers.add(analysis['id'])
        parameters = analysis['parameters']
        if not parameters or any(not isinstance(v, list) or not v for v in parameters.values()):
            raise ValueError(f"Parámetros vacíos o inválidos en {analysis['id']}.")
        if any(column not in parameters for column in analysis['columns']):
            raise ValueError(f"Columnas desconocidas en {analysis['id']}.")
        if not repetition_numbers(analysis):
            raise ValueError(f"Repeticiones vacías en {analysis['id']}.")
    return analyses


def repetition_numbers(analysis):
    repetitions = analysis['repetitions']
    return range(repetitions['start'], repetitions['stop'])


def analyze(analysis, root=None):
    """Group minimum results and steps by configuration and save the completed table.

    Relative paths are resolved from the project directory. A missing or invalid
    file stops the analysis to avoid publishing averages from incomplete data.
    """
    base = Path(root) if root is not None else ROOT
    parameters = analysis['parameters']
    rows = []
    numbers = repetition_numbers(analysis)
    if not numbers:
        raise ValueError('El rango de repeticiones no puede estar vacío.')
    for values in product(*parameters.values()):
        configuration = dict(zip(parameters, values))
        minimums, steps = [], []
        for number in numbers:
            path = base / analysis['input_template'].format(**configuration, number=number)
            try:
                frame = pd.read_excel(path)
            except FileNotFoundError as error:
                raise FileNotFoundError(f'Falta el archivo de resultados: {path}') from error
            if not {'Resultado', 'Step'}.issubset(frame.columns):
                raise ValueError(f'{path}: faltan las columnas Resultado o Step.')
            if frame.empty or frame['Resultado'].isna().all():
                raise ValueError(f'{path}: no contiene resultados válidos.')
            index = frame['Resultado'].idxmin()
            minimum = frame.loc[index, 'Resultado']
            step = frame.loc[index, 'Step']
            if pd.isna(step):
                raise ValueError(f'{path}: el resultado mínimo no tiene Step.')
            minimums.append(minimum)
            steps.append(step)
        row = {column: configuration[column] for column in analysis['columns']}
        row.update(zip(METRICS, (sum(minimums) / len(minimums),
                                sum(steps) / len(steps), min(minimums))))
        rows.append(row)
    table = pd.DataFrame(rows, columns=analysis['columns'] + METRICS)
    if analysis['output'] is not None:
        destination = base / analysis['output']
        destination.parent.mkdir(parents=True, exist_ok=True)
        table.to_excel(destination, index=False)
        print(f'Análisis guardado en {destination}')
    print(table.to_string(index=False))
    return table

