"""Configuration layout, inheritance, and compatibility checks."""


import numpy as np
import pytest

from tsp_pso.experiments.experiment_batch import build_presets, load_presets
from tsp_pso.experiments.experiment_config import RepetitionSpec
from tsp_pso.infrastructure.dataset_reader import load_dataset
from tsp_pso.infrastructure.experiment_options import (
    ROOT,
    load_catalog_options,
    load_preset_options,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('name, size, has_prices', [
    ('berlin52', 52, False), ('bays29', 29, False), ('st70', 70, False),
    ('ch150', 150, False), ('kroA100', 100, False), ('rat195', 195, False),
    ('Bahia30D', 30, True), ('Minas24D', 24, True),
    ('Minas30D', 30, True), ('Minas57D', 57, True),
])
def test_configured_dataset_loads(name, size, has_prices):
    dataset = load_catalog_options()['datasets'][name]
    assert dataset['source'] == ('Ottoni et al. (2022)' if has_prices else 'TSPLIB')
    assert dataset['problem_types'] == (['tsp', 'tspwr'] if has_prices else ['tsp'])
    assert dataset['filename'].startswith('Ottoni/' if has_prices else 'TSPLIB/')
    matrix, prices = load_dataset(dataset, ROOT / 'datasets')
    assert matrix.shape == (size, size)
    assert np.all(np.isfinite(matrix))
    if has_prices:
        assert prices.shape == (size,)
        assert np.all(np.isfinite(prices))
    else:
        assert prices is None


def test_experiment_count_and_order():
    assert len(load_catalog_options()['datasets']) == 10
    experiments = load_presets()
    assert len(experiments) == 22
    assert experiments == load_presets()
    assert [(e.datasets[0], e.legacy_label) for e in experiments] == [
        ('berlin52', 'individual'), ('bays29', 'individual'),
        ('st70', 'individual'), ('ch150', 'individual'),
        ('kroA100', 'individual'), ('rat195', 'individual'),
        ('Bahia30D', 'individual'), ('Minas24D', 'individual'),
        ('Minas30D', 'individual'), ('Minas57D', 'individual'),
        ('berlin52', 'c1 and probability sweep'), ('berlin52', 'Opt 21'),
        ('bays29', 'particle sweep'), ('st70', 'c1 sweep'),
        ('ch150', 'c1 sweep'), ('kroA100', 'repetitions 17–20'),
        ('rat195', 'repetitions 6–10'),
        ('Bahia30D', 'circuit and initial tank'),
        ('Minas24D', 'circuit and initial tank'),
        ('Minas30D', 'circuit and initial tank'),
        ('Minas57D', 'circuit and initial tank'),
        ('Minas24D', 'circuit fuel regression'),
    ]


def test_experiment_overrides_replace_defaults_shallowly():
    options = load_preset_options()
    options['defaults']['particles'] = [2, 4]
    options['defaults']['repetitions'] = {'start': 5, 'stop': 9}
    options['experiments'] = [{
        'dataset': 'Minas24D', 'label': 'override check', 'steps': [1200],
        'particles': [8], 'repetitions': {'start': 1, 'stop': 2},
    }]
    experiment, = build_presets(options)
    assert experiment.particles == (8,)
    assert experiment.repetitions == RepetitionSpec(1, 1)
    assert experiment.operators == (10,)
    assert experiment.reset_threshold_divisor[0] == 1000
    assert experiment.primary_operator_share[0] == 0.2
    assert experiment.progress_warmup_multiplier[0] == 5
    # A partial nested override must not inherit the missing key from defaults.
    options['experiments'][0]['repetitions'] = {'stop': 2}
    with pytest.raises(KeyError, match='start'):
        build_presets(options)
