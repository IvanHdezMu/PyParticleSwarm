# MITECO Spain derived instances

These are derived benchmark instances generated from real Spanish fuel stations,
not official MITECO benchmark datasets. Each selected station is treated as a
TSPWR node with coordinates and one reported fuel price. No prices are invented.

Source organization: Ministerio para la Transición Ecológica y el Reto
Demográfico (MITECO), Spain. Origen de los datos: Ministerio para la Transición
Ecológica y el Reto Demográfico.

Official structured JSON endpoint:

<https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/>

[Official REST service documentation](https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/help)
and [MITECO catalog resource](https://catalogo.datosabiertos.miteco.gob.es/catalogo/es/dataset/214e0895-b3aa-4662-8ebe-18134c21fb45/resource/d61f70f9-2e1f-464b-bc6a-39199776afd7).
No HTML scraping is used.

## License and provenance

[MITECO's general reuse terms](https://www.datosabiertos.miteco.gob.es/es/aviso-legal.html)
permit commercial and non-commercial reuse subject to their conditions, including
source attribution and preservation of the source update date. No separate
license specific to this dataset was verified; the dataset metadata records `license: null`
and links the general terms rather than assigning an unverified license.
These derived instances do not imply MITECO endorsement.

Each generated JSON dataset is self-contained, with two top-level fields:
`metadata` and `nodes`. Metadata contains the original source URL, source date,
source SHA-256, creation timestamp, region, fuel, size, seed, selected station
IDs, and generator version. Each node contains `id` (string), `latitude`,
`longitude`, and `price` (numbers).

The official input and generated output are both JSON. No Excel conversion is
performed. PyParticleSwarm loads the normalized dataset directly using
`format: "json"`, preserving node order and using the same geodesic distances
as its geographic Excel datasets. Metadata does not affect solver behavior.
This is a selection of source records, not an unmodified official download.
The source response is updated periodically; dates and prices describe the
saved snapshot, not necessarily today.

## Generation and replay

From the repository root:

```bash
python3 tools/dataset_generators/generate_miteco.py \
  --region "Comunidad de Madrid" --fuel "Gasóleo A" --size 20 --seed 42 \
  --save-snapshot /tmp/miteco-source.json
```

This produces `Comunidad de Madrid_20_seed42.json` here. Keep the snapshot in durable storage
for exact replay; `/tmp` is only an example temporary location. Pass
`--input /path/to/snapshot.json` with the same parameters and a fresh `--output`
path to reproduce the selected stations in the same order. Re-downloading the
live source can yield a different selection. Existing outputs are not overwritten.
The example dataset's full national source snapshot is not bundled in this
repository; its date/hash and selected IDs are in its metadata. The existing example preserves the original generation
metadata (generator version 1) and station order from before the JSON format
migration; new datasets use generator version 2.

See [generator instructions](../../tools/dataset_generators/README.md) for
filtering, parameters, and requirements. Generated datasets are not automatically
registered, and existing datasets, experiments, and solver behavior are unchanged.
