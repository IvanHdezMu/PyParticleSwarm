"""Configuration layout, inheritance, and compatibility checks."""

import json

import numpy as np
import pytest

from tsp_pso import runner
from tsp_pso.analysis import load_analysis_options

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('name, size, has_prices', [
    ('berlin52', 52, False), ('bays29', 29, False), ('st70', 70, False),
    ('ch150', 150, False), ('kroA100', 100, False), ('rat195', 195, False),
    ('Bahia30D', 30, True), ('Minas24D', 24, True),
    ('Minas30D', 30, True), ('Minas57D', 57, True),
])
def test_configured_dataset_loads(name, size, has_prices):
    dataset = runner.DATASETS[name]
    assert dataset['source'] == ('Ottoni et al. (2022)' if has_prices else 'TSPLIB')
    assert dataset['problem_types'] == (['tsp', 'tspwr'] if has_prices else ['tsp'])
    assert dataset['filename'].startswith('Ottoni/' if has_prices else 'TSPLIB/')
    matrix, prices = runner.load_dataset(name)
    assert matrix.shape == (size, size)
    assert np.all(np.isfinite(matrix))
    if has_prices:
        assert prices.shape == (size,)
        assert np.all(np.isfinite(prices))
    else:
        assert prices is None


def test_experiment_count_and_order():
    assert len(runner.DATASETS) == 10
    experiments = runner.build_experiments(runner.load_run_options())
    assert len(experiments) == 22
    assert experiments == runner.EXPERIMENTS
    assert [(e.dataset, e.label) for e in experiments] == [
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
    options = runner.load_run_options()
    options['defaults']['particles'] = [2, 4]
    options['defaults']['repetitions'] = {'start': 5, 'stop': 9}
    options['experiments'] = [{
        'dataset': 'Minas24D', 'label': 'override check', 'steps': [1200],
        'particles': [8], 'repetitions': {'start': 1, 'stop': 2},
    }]
    experiment, = runner.build_experiments(options)
    assert experiment.particles == (8,)
    assert experiment.repetitions == range(1, 2)
    assert experiment.opts == (10,)
    assert experiment.reset_threshold_divisor == 1000
    assert experiment.primary_operator_share == 0.2
    assert experiment.progress_warmup_multiplier == 5
    # A partial nested override must not inherit the missing key from defaults.
    options['experiments'][0]['repetitions'] = {'stop': 2}
    with pytest.raises(KeyError, match='start'):
        runner.build_experiments(options)


def test_historical_analyses_preserved():
    analyses = load_analysis_options()
    historical = analyses[:2]
    assert historical == runner.load_run_options()['historical_analyses']
    assert historical == [
        {
            'id': identifier, 'label': f'berlin52: {identifier} (historical)',
            'parameters': {'optType': [1, 2, 3, 4, 5]},
            'repetitions': {'start': 1, 'stop': 11},
            'input_template': f'Results/berlin52/{identifier}/berlin52_{{optType}}_{{number}}.xlsx',
            'columns': ['optType'], 'output': None,
        }
        for identifier in ('00', '02_08')
    ]
    assert len(analyses) == 24
    numbered = runner.analysis_menu_options(analyses)
    assert list(numbered) == list(range(1, 23))
    assert [(a['experiment']['dataset'], a['experiment']['label'])
            for a in numbered.values()] == [(e.dataset, e.label) for e in runner.EXPERIMENTS]


def test_split_config_uses_sibling_files(tmp_path):
    expected = runner.load_run_options()
    expected['output_dir'] = 'alternate-results'
    expected['defaults']['verbose'] = False
    expected['historical_analyses'] = []
    for filename, keys in [
        ('datasets.json', ['datasets']),
        ('experiments.json', ['output_dir', 'defaults', 'experiments']),
        ('historical_analyses.json', ['historical_analyses']),
    ]:
        (tmp_path / filename).write_text(json.dumps({key: expected[key] for key in keys}))
    assert runner.load_run_options(tmp_path / 'experiments.json') == expected
    assert len(load_analysis_options(tmp_path / 'experiments.json')) == 22


def test_explicit_combined_config_remains_supported(tmp_path):
    expected = runner.load_run_options()
    path = tmp_path / 'combined.json'
    path.write_text(json.dumps(expected))
    assert runner.load_run_options(path) == expected
