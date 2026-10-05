"""Generate loader-compatible TSPWR workbooks from official MITECO JSON."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import unicodedata
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd

SOURCE_URL = ('https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/'
              'PreciosCarburantes/EstacionesTerrestres/')
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / 'datasets' / 'MITECO_Spain'


def normalize(value):
    """Match exact names ignoring accents, case, and surrounding whitespace."""
    return ''.join(c for c in unicodedata.normalize('NFKD', value.strip().casefold())
                   if not unicodedata.combining(c))


def select_stations(snapshot, region, fuel, size, seed, region_field='Provincia'):
    if size <= 0:
        raise ValueError('Size must be positive')
    if region_field not in ('Provincia', 'Municipio'):
        raise ValueError('Region field must be Provincia or Municipio')
    rows = snapshot.get('ListaEESSPrecio')
    if snapshot.get('ResultadoConsulta', 'OK') != 'OK' or not isinstance(rows, list):
        raise ValueError('Invalid MITECO snapshot: expected a successful ListaEESSPrecio response')
    target = normalize(region)
    if region_field == 'Provincia' and target == 'comunidad de madrid':
        target = 'madrid'
    fuel_name = normalize(fuel)
    if fuel_name.startswith('precio '):
        fuel_name = fuel_name[7:]
    keys = {key for row in rows for key in row if key.startswith('Precio ')}
    matches = [key for key in keys if normalize(key[7:]) == fuel_name]
    if len(matches) != 1:
        raise ValueError(f'Unknown or ambiguous fuel: {fuel}')
    price_field = matches[0]
    valid = []
    for row in rows:
        if normalize(str(row.get(region_field, ''))) != target:
            continue
        try:
            lat, lon, price = (float(str(row.get(key, '')).strip().replace(',', '.'))
                               for key in ('Latitud', 'Longitud (WGS84)', price_field))
        except (ValueError, TypeError):
            continue
        if not all(math.isfinite(value) for value in (lat, lon, price)):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or price <= 0:
            continue
        valid.append({'station_id': str(row.get('IDEESS') or ''),
                      'latitude': lat, 'longitude': lon, 'price': price})
    if len(valid) < size:
        raise ValueError(f'Requested {size} stations, but only {len(valid)} valid stations '
                         f'match {region!r} and {fuel!r}')
    # Canonical ordering makes selection independent of the service row order.
    valid.sort(key=lambda row: (row['station_id'], row['latitude'], row['longitude'], row['price']))
    return random.Random(seed).sample(valid, size), len(rows), len(valid), price_field


def generate(raw, region, fuel, size, seed, output=None, region_field='Provincia'):
    selected, inspected, valid, price_field = select_stations(
        json.loads(raw), region, fuel, size, seed, region_field)
    if output is None:
        safe_region = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', region.strip()).rstrip('. ')
        if not safe_region:
            raise ValueError('Region must have a usable filename')
        output = DEFAULT_OUTPUT / f'{safe_region}_{size}_seed{seed}.xlsx'
    output = Path(output)
    if output.suffix.lower() != '.xlsx':
        raise ValueError('Output must be an .xlsx file')
    sidecar = output.with_suffix('.json')
    if output.exists() or sidecar.exists():
        raise ValueError(f'Output already exists: {output} or {sidecar}')
    metadata = {
        'source': 'MITECO Spain', 'source_url': SOURCE_URL,
        'source_organization': 'Ministerio para la Transición Ecológica y el Reto Demográfico',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source_date': json.loads(raw).get('Fecha'),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'region': region, 'region_field': region_field, 'fuel': fuel,
        'price_field': price_field, 'size': size, 'seed': seed,
        'source_rows': inspected, 'valid_rows': valid,
        'selected_station_ids': [row['station_id'] for row in selected],
        'license': None,
        'license_url': 'https://www.datosabiertos.miteco.gob.es/es/aviso-legal.html',
        'license_note': 'General MITECO reuse terms; no dataset-specific license verified.',
        'generator': 'tools/dataset_generators/generate_miteco.py',
        'generator_version': 1,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(selected).to_excel(output, index=False)
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', required=True, help='Exact province or municipality name')
    parser.add_argument('--region-field', choices=('Provincia', 'Municipio'), default='Provincia')
    parser.add_argument('--fuel', required=True, help='Official fuel name, e.g. Gasóleo A')
    parser.add_argument('--size', required=True, type=int)
    parser.add_argument('--seed', required=True, type=int)
    parser.add_argument('--output', type=Path, help='Destination .xlsx file')
    parser.add_argument('--input', type=Path, help='Use a saved official JSON snapshot offline')
    parser.add_argument('--save-snapshot', type=Path, help='Save the exact source JSON for later replay')
    args = parser.parse_args(argv)
    try:
        if args.input:
            raw = args.input.read_bytes()
        else:
            with urlopen(SOURCE_URL, timeout=60) as response:
                raw = response.read()
        if args.save_snapshot:
            args.save_snapshot.parent.mkdir(parents=True, exist_ok=True)
            with args.save_snapshot.open('xb') as stream:
                stream.write(raw)
        output, metadata = generate(raw, args.region, args.fuel, args.size, args.seed,
                                    args.output, args.region_field)
    except (ValueError, OSError, URLError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(f"Inspected {metadata['source_rows']} source rows; {metadata['valid_rows']} valid; "
          f"selected {metadata['size']} stations.\n{output}\n{output.with_suffix('.json')}")


if __name__ == '__main__':
    main()
