"""Dataset formats, path resolution and compatibility of the extracted reader."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from geopy import distance

from tsp_pso.infrastructure.dataset_reader import load_dataset

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('absolute', [False, True])
@pytest.mark.parametrize('fmt', ['euc', 'matrix', 'json', 'excel'])
def test_formats_values_types_and_paths(tmp_path, monkeypatch, absolute, fmt):
    root = tmp_path / 'datasets'
    root.mkdir()
    path = root / ('sample.xlsx' if fmt == 'excel' else 'sample.txt')
    if fmt == 'euc':
        # Preserve the TSPLIB reader's node indices and coordinate truncation.
        path.write_text('DIMENSION: 3\nNODE_COORD_SECTION\n3 3.9 4.9\n1 0 0\n2 1.9 1.9\n')
        expected = np.array([[0., 1., 5.], [1., 0., 4.], [5., 4., 0.]])
        expected_prices = None
    elif fmt == 'matrix':
        path.write_text('DIMENSION: 3\nEDGE_WEIGHT_FORMAT: FULL_MATRIX\nEDGE_WEIGHT_SECTION\n0 2 3\n4 0 6\n7 8 0\n')
        expected = np.array([[0., 2., 3.], [4., 0., 6.], [7., 8., 0.]])
        expected_prices = None
    else:
        coordinates = [(0, 1), (0, 0), (1, 0)]
        expected_prices = np.array([3., 1., 2.])
        if fmt == 'json':
            path.write_text(json.dumps({'metadata': {'ignored': True}, 'nodes': [
                {'id': name, 'latitude': lat, 'longitude': lon, 'price': price}
                for name, (lat, lon), price in zip(['z', 'a', 'm'], coordinates, expected_prices)
            ]}))
        else:
            pd.DataFrame({'id': ['z', 'a', 'm'], 'lat': [0, 0, 1], 'lon': [1, 0, 0],
                          'price': [3, 1, 2], 'ignored': [9, 9, 9]}).to_excel(path, index=False)
            expected_prices = np.array([3, 1, 2], dtype=np.int64)
        expected = np.array([[0. if i == j else distance.distance(coordinates[i], coordinates[j]).km
                              for j in range(3)] for i in range(3)])
    monkeypatch.chdir(tmp_path)
    descriptor = {'filename': str(path) if absolute else path.name, 'format': fmt}
    matrix, prices = load_dataset(descriptor, Path('missing') if absolute else Path('datasets'))
    assert type(matrix) is np.ndarray
    assert matrix.dtype == expected.dtype
    assert matrix.shape == (3, 3)
    np.testing.assert_array_equal(matrix, expected)
    if expected_prices is None:
        assert prices is None
    else:
        assert type(prices) is np.ndarray
        assert prices.dtype == expected_prices.dtype
        assert prices.shape == (3,)
        np.testing.assert_array_equal(prices, expected_prices)


@pytest.mark.parametrize('descriptor,error,message', [
    ({}, KeyError, 'format'),
    ({'format': 'json'}, KeyError, 'filename'),
    ({'format': 'unsupported', 'filename': 'missing'}, ValueError, 'Unknown dataset format: unsupported'),
    ({'format': 'json', 'filename': 'missing'}, FileNotFoundError, 'missing'),
])
def test_reader_errors(tmp_path, descriptor, error, message):
    with pytest.raises(error, match=message):
        load_dataset(descriptor, tmp_path)


def test_runner_wrapper_and_batch_catalog(tmp_path, monkeypatch):
    from tsp_pso.application import runner
    from tsp_pso.experiments import batch_executor

    root = tmp_path / 'datasets'
    root.mkdir()
    (root / 'sample.json').write_text(json.dumps({'nodes': [
        {'latitude': 0, 'longitude': 0, 'price': 1.5}]}))
    original = {'filename': 'missing', 'format': 'json'}
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'DATASETS', {'sample': original})
    with pytest.raises(KeyError, match='absent'):
        runner.load_dataset('absent')
    descriptor = SimpleNamespace(id='sample', filename='sample.json', format='json',
                                 source='test', problem_types=('tspwr',))
    monkeypatch.setattr(batch_executor, 'to_legacy_experiment', lambda run: run)
    def execute(run, output_dir):
        matrix, prices = runner.load_dataset('sample')
        np.testing.assert_array_equal(matrix, [[0.]])
        np.testing.assert_array_equal(prices, [1.5])
        return output_dir
    monkeypatch.setattr(runner, 'execute', execute)
    assert batch_executor.execute_one(object(), tmp_path, descriptor) == tmp_path
    assert runner.DATASETS['sample'] is original


def test_import_does_not_load_runner():
    result = subprocess.run([sys.executable, '-B', '-c',
        'import sys; from tsp_pso.infrastructure.dataset_reader import load_dataset; '
        'assert "tsp_pso.application.runner" not in sys.modules'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
