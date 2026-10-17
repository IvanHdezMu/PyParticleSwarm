"""Dataset reading independent of the experiment catalog and application runner."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from geopy import distance

from .tsplib.euc2d import read_euc2d_matrix
from .tsplib.geo import read_geo_matrix


def load_dataset(dataset, datasets_root):
    """Read a descriptor's filename relative to datasets_root, or as an absolute path.

    The descriptor must provide filename and format. Supported formats are euc
    (rounded TSPLIB Euclidean distances), matrix (TSPLIB edge weights), json
    (nodes with latitude, longitude and price), and excel (coordinates in columns
    1:3 and prices in column 3). Geographic distances are in kilometres.
    Return (distance matrix, prices), with prices=None for TSPLIB. Node order
    and numeric conversions follow the existing readers; metadata is not returned.
    File, descriptor and parsing errors propagate without translation.
    """
    fmt = dataset['format']
    path = Path(datasets_root) / dataset['filename']
    if fmt == 'euc':
        return np.round(read_euc2d_matrix(path), 0), None
    if fmt == 'matrix':
        return read_geo_matrix(path), None
    if fmt == 'json':
        with path.open(encoding='utf-8') as stream:
            nodes = json.load(stream)['nodes']
        coordinates = np.array([[node['latitude'], node['longitude']] for node in nodes], dtype=float)
        prices = np.array([node['price'] for node in nodes], dtype=float)
    elif fmt == 'excel':
        df = pd.read_excel(path)
        coordinates = df.iloc[:, 1:3].to_numpy()
        prices = df.iloc[:, 3].to_numpy()
    else:
        raise ValueError(f'Unknown dataset format: {fmt}')
    matrix = np.zeros((len(coordinates), len(coordinates)))
    for i, start in enumerate(coordinates):
        for j in range(i + 1, len(coordinates)):
            matrix[i, j] = matrix[j, i] = distance.distance(start, coordinates[j]).km
    return matrix, prices

