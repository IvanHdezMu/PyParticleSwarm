# MITECO dataset generator

Generate derived TSPWR instances from Spanish fuel stations without changing the
solver or registering datasets in `config/datasets.json`. Each station is one
node with its reported coordinates and selected fuel price.

## Requirements and usage

Use Python 3.12 and the existing dependencies:

```bash
python3 -m pip install -r .devcontainer/requirements.txt
python3 tools/dataset_generators/generate_miteco.py \
  --region "Comunidad de Madrid" --fuel "Gasóleo A" --size 20 --seed 42 \
  --save-snapshot /tmp/miteco-source.json
```

Replay a saved snapshot (no network required), choosing another destination:

```bash
python3 tools/dataset_generators/generate_miteco.py \
  --input /tmp/miteco-source.json \
  --region "Comunidad de Madrid" --fuel "Gasóleo A" --size 20 --seed 42 \
  --output /tmp/Madrid_20_seed42.xlsx
```

The default destination is `datasets/MITECO_Spain/` relative to the repository,
independent of the current working directory. The default filename is
`<region>_<size>_seed<seed>.xlsx`; unsafe filename characters are replaced.
Existing workbooks, sidecars, and saved snapshots are not overwritten. Different
fuels can share a default name; use `--output` to distinguish them.

| Argument | Meaning |
| --- | --- |
| `--region` | Required exact province name, or municipality with `--region-field Municipio`. |
| `--region-field` | `Provincia` (default) or `Municipio`. |
| `--fuel` | Required official fuel name, e.g. `Gasóleo A` or `Gasolina 95 E5`; optional `Precio ` prefix. |
| `--size` | Required positive number of stations. |
| `--seed` | Required integer seed for deterministic sampling without replacement. |
| `--output` | Optional full destination `.xlsx` path. |
| `--input` | Optional saved official JSON snapshot instead of a live download. |
| `--save-snapshot` | Optional path to preserve the exact input bytes for replay. |

Matching ignores accents, case, and surrounding whitespace; there is no fuzzy
matching. `Comunidad de Madrid` explicitly aliases province `Madrid`. Other
multi-province autonomous communities are not supported as region names in this
first version; choose a province. Municipality names are matched across the
national snapshot, so names shared by several provinces select all matches.

## Selection and output

Consumed fields are `ListaEESSPrecio`, `ResultadoConsulta`, `Fecha`, `IDEESS`,
`Provincia` or `Municipio`, `Latitud`, `Longitud (WGS84)`, and the selected
`Precio ...` field. Decimal commas are converted to numbers. Rows with missing,
non-numeric, non-finite, or out-of-range coordinates, or missing/non-positive/
non-finite prices, are excluded. Missing prices are never filled. Unknown fuel
names and insufficient valid stations produce errors, not smaller datasets.

Candidates are sorted by station ID, coordinates, and price before sampling with
a local seeded random generator. Given identical snapshot data, region, fuel,
size, seed, and generator version, selected stations have the same order. The
live service changes over time: a seed alone cannot reproduce a past download.
Keep `--save-snapshot` output for exact replay; the sidecar's SHA-256 identifies
its bytes but does not replace the snapshot. Workbooks and metadata are not
byte-identical across generations because creation timestamps can differ.

The Excel columns are `station_id`, `latitude`, `longitude`, `price`, in that
order, with no extra index column. This matches the existing Excel loader's
positional interpretation. IDs are retained in the workbook and as strings in
the JSON sidecar; missing IDs are empty strings. The sidecar also records source,
source date/hash, generation time, selection parameters, row counts, and reuse
information. Metadata does not affect solver behavior. Fuel prices retain the
source's units; Gasóleo A and gasoline prices are EUR/L. When choosing another
product, check that its units are compatible with the experiment's capacity and
consumption settings. Coordinates produce the project's existing geodesic
route distances, not road-network distances.

See [source and provenance](../../datasets/MITECO_Spain/README.md) for the exact
endpoint and reuse terms. Tests use synthetic in-memory snapshots and never
require the live service.
