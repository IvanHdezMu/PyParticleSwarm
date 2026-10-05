"""Offline checks for the official-source dataset generator."""

import hashlib
import json

import numpy as np
import pandas as pd
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
    assert len({row['station_id'] for row in first[0]}) == 4
    snapshot['ListaEESSPrecio'].reverse()
    assert first == generator.select_stations(snapshot, 'Comunidad de Madrid', 'Gasóleo A', 4, 42)


def test_region_and_fuel_filtering(snapshot):
    snapshot['ListaEESSPrecio'][0]['Provincia'] = 'TOLEDO'
    snapshot['ListaEESSPrecio'][1]['Precio Gasoleo A'] = ''
    selected, total, valid, field = generator.select_stations(snapshot, 'madrid', 'Gasóleo A', 6, 42)
    assert (total, valid, field) == (8, 6, 'Precio Gasoleo A')
    assert {row['station_id'] for row in selected} == set(map(str, range(2, 8)))
    assert all(row['price'] == 1.499 for row in selected)
    petrol, _, valid, _ = generator.select_stations(snapshot, 'MADRID', 'Gasolina 95 E5', 7, 42)
    assert valid == 7
    assert all(row['price'] == 1.699 for row in petrol)
    snapshot['ListaEESSPrecio'][2]['Municipio'] = 'Alcalá de Henares'
    rows, _, valid, _ = generator.select_stations(
        snapshot, 'alcala de henares', 'Gasóleo A', 1, 42, 'Municipio')
    assert valid == 1
    assert rows[0]['station_id'] == '2'


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
    assert '0' not in [row['station_id'] for row in selected]


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
    output, metadata = generator.generate(raw, 'Madrid', 'Gasóleo A', 3, 42, tmp_path / 'sample.xlsx')
    frame = pd.read_excel(output)
    assert list(frame.columns) == ['station_id', 'latitude', 'longitude', 'price']
    assert frame.shape == (3, 4)
    selected = generator.select_stations(snapshot, 'Madrid', 'Gasóleo A', 3, 42)[0]
    np.testing.assert_allclose(frame.iloc[:, 1:].to_numpy(),
                               [[r['latitude'], r['longitude'], r['price']] for r in selected])
    monkeypatch.setattr(runner, 'DATASETS', {'sample': {'filename': str(output), 'format': 'excel'}})
    matrix, prices = runner.load_dataset('sample')
    assert matrix.shape == (3, 3)
    assert np.all(np.isfinite(matrix))
    np.testing.assert_allclose(matrix, matrix.T)
    np.testing.assert_array_equal(np.diag(matrix), np.zeros(3))
    np.testing.assert_allclose(prices, [1.499] * 3)
    assert json.loads(output.with_suffix('.json').read_text()) == metadata
    assert metadata['selected_station_ids'] == [r['station_id'] for r in selected]
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
    assert (tmp_path / 'Comunidad de Madrid_3_seed42.xlsx').exists()
    assert (tmp_path / 'saved.json').read_bytes() == source.read_bytes()
    assert 'Inspected 8 source rows; 8 valid; selected 3 stations.' in capsys.readouterr().out
