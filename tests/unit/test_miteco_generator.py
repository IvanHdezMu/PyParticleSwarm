"""Offline checks for the official-source dataset generator."""

import hashlib
import json

import numpy as np
import pytest

from tools.dataset_generators import generate_miteco as generator
from tsp_pso import runner

pytestmark = pytest.mark.unit


@pytest.fixture
def snapshot():
    return {
        'Fecha': '01/10/2026 12:00:00', 'ResultadoConsulta': 'OK',
        'ListaEESSPrecio': [
            {'IDEESS': str(i), 'Provincia': 'MADRID', 'Municipio': 'Madrid',
             'Latitud': f'40,{i + 10}', 'Longitud (WGS84)': '-3,700',
             'Precio Gasoleo A': '1,499', 'Precio Gasolina 95 E5': '1,699'}
            for i in range(8)
        ],
    }


def test_selection_is_repeatable_and_seed_sensitive(snapshot):
    first = generator.select_stations(snapshot, 'Comunidad de Madrid', 'Gasóleo A', 4, 42)
    assert first == generator.select_stations(snapshot, 'Comunidad de Madrid', 'Gasóleo A', 4, 42)
    assert first[0] != generator.select_stations(snapshot, 'Comunidad de Madrid', 'Gasóleo A', 4, 7)[0]
    assert len({row['id'] for row in first[0]}) == 4
    snapshot['ListaEESSPrecio'].reverse()
    assert first == generator.select_stations(snapshot, 'Comunidad de Madrid', 'Gasóleo A', 4, 42)


def test_region_and_fuel_filtering(snapshot):
    snapshot['ListaEESSPrecio'][0]['Provincia'] = 'TOLEDO'
    snapshot['ListaEESSPrecio'][1]['Precio Gasoleo A'] = ''
    selected, total, valid, field = generator.select_stations(snapshot, 'madrid', 'Gasóleo A', 6, 42)
    assert (total, valid, field) == (8, 6, 'Precio Gasoleo A')
    assert {row['id'] for row in selected} == set(map(str, range(2, 8)))
    assert all(row['price'] == 1.499 for row in selected)
    petrol, _, valid, _ = generator.select_stations(snapshot, 'MADRID', 'Gasolina 95 E5', 7, 42)
    assert valid == 7
    assert all(row['price'] == 1.699 for row in petrol)
    snapshot['ListaEESSPrecio'][2]['Municipio'] = 'Alcalá de Henares'
    rows, _, valid, _ = generator.select_stations(
        snapshot, 'alcala de henares', 'Gasóleo A', 1, 42, 'Municipio')
    assert valid == 1
    assert rows[0]['id'] == '2'


@pytest.mark.parametrize('field,value', [
    ('Latitud', ''), ('Latitud', None), ('Latitud', 'bad'), ('Latitud', '91'),
    ('Latitud', '-91'), ('Latitud', 'nan'), ('Longitud (WGS84)', '181'),
    ('Longitud (WGS84)', '-181'), ('Longitud (WGS84)', 'inf'),
    ('Precio Gasoleo A', ''), ('Precio Gasoleo A', None), ('Precio Gasoleo A', 'bad'),
    ('Precio Gasoleo A', '0'), ('Precio Gasoleo A', '-1'), ('Precio Gasoleo A', 'nan'),
])
def test_invalid_station_is_excluded(snapshot, field, value):
    snapshot['ListaEESSPrecio'][0][field] = value
    selected, total, valid, _ = generator.select_stations(snapshot, 'Madrid', 'Gasóleo A', 7, 42)
    assert (total, valid) == (8, 7)
    assert '0' not in [row['id'] for row in selected]


def test_insufficient_stations_and_unknown_fuel_fail(snapshot):
    with pytest.raises(ValueError, match='Requested 9 stations, but only 8 valid'):
        generator.select_stations(snapshot, 'Madrid', 'Gasóleo A', 9, 42)
    with pytest.raises(ValueError, match='only 0 valid'):
        generator.select_stations(snapshot, 'Missing region', 'Gasóleo A', 1, 42)
    with pytest.raises(ValueError, match='Unknown or ambiguous fuel'):
        generator.select_stations(snapshot, 'Madrid', 'Imaginary fuel', 1, 42)
    with pytest.raises(ValueError, match='Size must be positive'):
        generator.select_stations(snapshot, 'Madrid', 'Gasóleo A', 0, 42)


def test_output_loads_with_existing_loader(snapshot, tmp_path, monkeypatch):
    raw = json.dumps(snapshot).encode()
    output, metadata = generator.generate(raw, 'Madrid', 'Gasóleo A', 3, 42, tmp_path / 'sample.json')
    dataset = json.loads(output.read_text())
    assert set(dataset) == {'metadata', 'nodes'}
    selected = generator.select_stations(snapshot, 'Madrid', 'Gasóleo A', 3, 42)[0]
    assert dataset['nodes'] == selected
    assert all(set(node) == {'id', 'latitude', 'longitude', 'price'} for node in dataset['nodes'])
    second, _ = generator.generate(raw, 'Madrid', 'Gasóleo A', 3, 42, tmp_path / 'second.json')
    assert json.loads(second.read_text())['nodes'] == dataset['nodes']
    assert not list(tmp_path.glob('*.xlsx'))
    monkeypatch.setattr(runner, 'DATASETS', {'sample': {'filename': str(output), 'format': 'json'}})
    matrix, prices = runner.load_dataset('sample')
    assert matrix.shape == (3, 3)
    assert np.all(np.isfinite(matrix))
    np.testing.assert_allclose(matrix, matrix.T)
    np.testing.assert_array_equal(np.diag(matrix), np.zeros(3))
    np.testing.assert_allclose(prices, [1.499] * 3)
    assert dataset['metadata'] == metadata
    assert {'source', 'generated_at', 'region', 'fuel', 'size', 'seed'} <= metadata.keys()
    assert metadata['selected_station_ids'] == [r['id'] for r in selected]
    assert metadata['source_sha256'] == hashlib.sha256(raw).hexdigest()
    assert metadata['source_date'] == snapshot['Fecha']
    assert metadata['source_url'] == generator.SOURCE_URL
    assert (metadata['size'], metadata['seed'], metadata['source_rows'], metadata['valid_rows']) == (3, 42, 8, 8)
    with pytest.raises(ValueError, match='Output already exists'):
        generator.generate(raw, 'Madrid', 'Gasóleo A', 3, 42, output)


def test_offline_cli_and_default_filename(snapshot, tmp_path, monkeypatch, capsys):
    source = tmp_path / 'source.json'
    source.write_text(json.dumps(snapshot))
    monkeypatch.setattr(generator, 'DEFAULT_OUTPUT', tmp_path)
    def no_network(*args, **kwargs):
        pytest.fail('Offline generation must not access the network')
    monkeypatch.setattr(generator, 'urlopen', no_network)
    generator.main(['--input', str(source), '--region', 'Comunidad de Madrid',
                    '--fuel', 'Gasóleo A', '--size', '3', '--seed', '42',
                    '--save-snapshot', str(tmp_path / 'saved.json')])
    assert (tmp_path / 'Comunidad de Madrid_3_seed42.json').exists()
    assert (tmp_path / 'saved.json').read_bytes() == source.read_bytes()
    assert 'Inspected 8 source rows; 8 valid; selected 3 stations.' in capsys.readouterr().out


def test_json_loader_preserves_order_and_geographic_distances(tmp_path, monkeypatch):
    path = tmp_path / 'coordinates.json'
    path.write_text(json.dumps({'metadata': {}, 'nodes': [
        {'id': 'b', 'latitude': 0, 'longitude': 1, 'price': 1.8},
        {'id': 'a', 'latitude': 0, 'longitude': 0, 'price': 1.2},
        {'id': 'c', 'latitude': 1, 'longitude': 0, 'price': 1.5},
    ]}))
    monkeypatch.setattr(runner, 'DATASETS', {'sample': {'filename': str(path), 'format': 'json'}})
    matrix, prices = runner.load_dataset('sample')
    # WGS84 geodesic distances in km, matching the existing Excel semantics.
    np.testing.assert_allclose(matrix, [
        [0, 111.319490793, 156.899568291],
        [111.319490793, 0, 110.574388558],
        [156.899568291, 110.574388558, 0],
    ], rtol=0, atol=1e-8)
    np.testing.assert_array_equal(prices, [1.8, 1.2, 1.5])


def test_json_and_existing_ottoni_excel_have_identical_values(tmp_path, monkeypatch):
    import pandas as pd

    expected_matrix, expected_prices = runner.load_dataset('Minas24D')
    frame = pd.read_excel(runner.ROOT / 'datasets' / runner.DATASETS['Minas24D']['filename'])
    path = tmp_path / 'ottoni.json'
    path.write_text(json.dumps({'metadata': {}, 'nodes': [
        {'id': str(row[0]), 'latitude': row[1], 'longitude': row[2], 'price': row[3]}
        for row in frame.itertuples(index=False, name=None)
    ]}))
    monkeypatch.setattr(runner, 'DATASETS', {'sample': {'filename': str(path), 'format': 'json'}})
    matrix, prices = runner.load_dataset('sample')
    np.testing.assert_array_equal(matrix, expected_matrix)
    np.testing.assert_array_equal(prices, expected_prices)
