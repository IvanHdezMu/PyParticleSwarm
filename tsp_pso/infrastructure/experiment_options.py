"""Read experiment options without importing the application runner."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_run_options(path=None):
    """Read combined options or merge the configuration's sibling JSON files.

    With no path (or a falsey path), use config/experiments.json under the
    project root. Explicit relative paths are relative to the working directory;
    absolute paths are used as supplied. If the JSON contains datasets, return
    it unchanged. Otherwise load datasets.json and historical_analyses.json from
    the same directory. File, JSON and missing-key errors propagate unchanged.
    """
    path = Path(path or ROOT / 'config' / 'experiments.json')
    with path.open(encoding='utf-8') as stream:
        options = json.load(stream)
    if 'datasets' in options:
        return options
    for section in ('datasets', 'historical_analyses'):
        with path.with_name(f'{section}.json').open(encoding='utf-8') as stream:
            options[section] = json.load(stream)[section]
    return options
