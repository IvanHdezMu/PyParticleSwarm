"""Read experiment options without importing the application runner."""

import json
from pathlib import Path

# ROOT: Project root directory used to resolve configuration file paths.
ROOT = Path(__file__).resolve().parents[2]


def load_catalog_options(path=None):
    """Read only the catalog JSON, without constructing dataset descriptors.

    A missing or falsey path selects config/datasets.json under ROOT. Explicit
    relative paths use the working directory; absolute paths are used as given.
    Return the decoded value unchanged; file and JSON errors propagate.
    """
    path = Path(path or ROOT / 'config' / 'datasets.json')
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def load_preset_options(path=None):
    """Read only the preset JSON, without merging sibling configuration files.

    A missing or falsey path selects config/experiments.json under ROOT. Explicit
    relative paths use the working directory; absolute paths are used as given.
    Return the decoded value unchanged; file and JSON errors propagate.
    """
    path = Path(path or ROOT / 'config' / 'experiments.json')
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)
