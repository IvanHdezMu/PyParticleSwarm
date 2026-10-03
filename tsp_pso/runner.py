"""Configure, run, and select TSP particle swarm experiments."""
from dataclasses import dataclass
from itertools import product
import json
from math import prod
from pathlib import Path

import numpy as np
import pandas as pd
from geopy import distance
from .solver import ParticleSwarm_VarOptMultiprocess
from .tsplib.euc2d import read_euc2d_matrix
from .tsplib.geo import read_geo_matrix

ROOT = Path(__file__).resolve().parents[1]


def load_run_options(path=None):
    path = Path(path or ROOT / 'config' / 'experiments.json')
    with path.open(encoding='utf-8') as stream:
        options = json.load(stream)
    # Preserve support for explicitly supplied combined configuration files.
    if 'datasets' in options:
        return options
    for section in ('datasets', 'historical_analyses'):
        with path.with_name(f'{section}.json').open(encoding='utf-8') as stream:
            options[section] = json.load(stream)[section]
    return options


RUN_OPTIONS = load_run_options()
DATASETS = RUN_OPTIONS['datasets']

@dataclass(frozen=True)
class Experiment:
    dataset: str
    label: str
    steps: tuple
    particles: tuple = (8,)
    opts: tuple = (10,)
    minimums: tuple = (0.2,)
    maximums: tuple = (0.8,)
    rings: tuple = (True,)
    full_tanks: tuple = (False,)
    repetitions: range = range(1, 2)
    excel: bool = False
    refuel: bool = False
    style: str = 'standard'
    max_capacity: float = 150.0
    consumption: float = 7.0
    permut_reset: bool = True
    k: int = 10
    analysis_output: str | None = None
    reset_threshold_divisor: float = 1000
    primary_operator_share: float = 0.2
    progress_warmup_multiplier: float = 5
    verbose: bool = True

    def configurations(self):
        return product(self.particles, self.steps, self.opts, self.minimums,
                       self.maximums, self.rings, self.full_tanks, self.repetitions)

    @property
    def count(self):
        return prod(len(values) for values in (self.particles, self.steps, self.opts,
                    self.minimums, self.maximums, self.rings, self.full_tanks, self.repetitions))


def build_experiments(options=None):
    options = RUN_OPTIONS if options is None else options
    experiments = []
    for entry in options['experiments']:
        values = {**options['defaults'], **entry}
        if values['dataset'] not in options['datasets']:
            raise ValueError(f"Unknown dataset: {values['dataset']}")
        for field in ('steps', 'particles', 'opts', 'minimums', 'maximums',
                      'rings', 'full_tanks'):
            if not isinstance(values[field], list) or not values[field]:
                raise ValueError(f"{field} must be a non-empty list.")
            values[field] = tuple(values[field])
        repetitions = values['repetitions']
        values['repetitions'] = range(repetitions['start'], repetitions['stop'])
        if not values['repetitions']:
            raise ValueError('The repetition range cannot be empty.')
        experiments.append(Experiment(**values))
    return experiments

EXPERIMENTS = build_experiments()


def load_dataset(name):
    dataset = DATASETS[name]
    fmt = dataset['format']
    path = ROOT / 'Datasets' / dataset['filename']
    if fmt == 'euc':
        return np.round(read_euc2d_matrix(path), 0), None
    if fmt == 'matrix':
        return read_geo_matrix(path), None
    if fmt != 'excel':
        raise ValueError(f'Unknown dataset format: {fmt}')
    df = pd.read_excel(path)
    coordinates = df.iloc[:, 1:3].to_numpy()
    matrix = np.zeros((len(coordinates), len(coordinates)))
    for i, start in enumerate(coordinates):
        for j in range(i + 1, len(coordinates)):
            matrix[i, j] = matrix[j, i] = distance.distance(start, coordinates[j]).km
    return matrix, df.iloc[:, 3].to_numpy()


def result_filename(experiment, configuration):
    n, c1, opt, minimum, maximum, ring, full, number = configuration
    prefix = f'{experiment.dataset}_True_{n}_{c1}_{opt}'
    if experiment.style == 'fuel':
        suffix = f'{ring}_{full}_{number}'
    elif experiment.style == 'bays':
        suffix = str(number)
    elif experiment.style == 'berlin_grid':
        suffix = f'{experiment.k}_{number}_{minimum}_{maximum}'
    else:
        suffix = f'{experiment.k}_{minimum}_{maximum}_{number}'
    return f'{prefix}_{suffix}.xlsx'


def execute(experiment, output_dir=None):
    matrix, prices = load_dataset(experiment.dataset)
    destination = (Path(output_dir) if output_dir is not None
                   else ROOT / RUN_OPTIONS['output_dir']) / experiment.dataset
    if experiment.excel:
        destination.mkdir(parents=True, exist_ok=True)
    for index, configuration in enumerate(experiment.configurations(), 1):
        n, c1, opt, minimum, maximum, ring, full, _ = configuration
        print(f'\nRun {index}/{experiment.count}: N={n}, c1={c1}, '
              f'Opt={opt}, circuit={ring}, full tank={full}')
        algorithm = ParticleSwarm_VarOptMultiprocess(
            N=n, c1=c1, distance_matrix=matrix, ring_mode=ring,
            refuel_mode=experiment.refuel, prices=prices,
            maxCapacity=experiment.max_capacity, consumption=experiment.consumption, fullinit=full,
            resetThresholdDivisor=experiment.reset_threshold_divisor,
            primaryOperatorShare=experiment.primary_operator_share,
            progressWarmupMultiplier=experiment.progress_warmup_multiplier)
        algorithm.run(verbose=experiment.verbose
                      and (experiment.label == 'individual' or not experiment.excel),
                      optType=opt, excel=experiment.excel,
                      file_path=destination / result_filename(experiment, configuration),
                      permutReset=experiment.permut_reset, minPermut=minimum,
                      maxPermut=maximum, k=experiment.k)
        if experiment.dataset == 'bays29' and (experiment.label == 'individual' or not experiment.excel):
            print(algorithm.nIter)


def choose_option(title, options, describe, numbers=None):
    numbered_options = dict(zip(numbers if numbers is not None else range(1, len(options) + 1),
                                options))
    print(f'\n{title}')
    for number, option in numbered_options.items():
        print(f'{number:2}. {describe(option)}')
    print(' 0. Exit')
    while True:
        try:
            choice = int(input('\nNumber: '))
        except ValueError:
            print('Enter a number from the menu.')
            continue
        if choice == 0:
            return None
        if choice in numbered_options:
            return numbered_options[choice]
        print('That number is not on the menu.')


def choose_experiment():
    return choose_option('What do you want to run?', EXPERIMENTS,
                         lambda experiment: f'{experiment.dataset}: {experiment.label} '
                         f'({experiment.count} runs)')


def analysis_menu_options(analyses):
    """Show the same experiments in the same order as run."""
    by_experiment = {(a['experiment']['dataset'], a['experiment']['label']): a
                     for a in analyses if 'experiment' in a}
    return {number: by_experiment[(experiment.dataset, experiment.label)]
            for number, experiment in enumerate(EXPERIMENTS, 1)}


def main():
    try:
        mode = choose_option('What do you want to do?', ('run', 'analysis'),
                             lambda mode: 'run — Execute' if mode == 'run' else 'analysis — Analyze results')
        if mode == 'run':
            experiment = choose_experiment()
            if experiment is not None:
                execute(experiment)
        elif mode == 'analysis':
            from .analysis import analyze, first_missing_result, load_analysis_options
            numbered = analysis_menu_options(load_analysis_options())
            counts = {(experiment.dataset, experiment.label): experiment.count
                      for experiment in EXPERIMENTS}
            analysis = choose_option('Which results do you want to analyze?', list(numbered.values()),
                                     lambda option: f"{option['label']} "
                                     f"({counts[(option['experiment']['dataset'], option['experiment']['label'])]} runs)",
                                     numbers=numbered)
            if analysis is not None:
                number = next(number for number, item in numbered.items() if item is analysis)
                missing = first_missing_result(analysis)
                if missing is not None:
                    print(f'Missing results for option {number}: {missing}')
                    if input(f'Run option {number} now? [y/N]: ').strip().lower() not in ('y', 'yes'):
                        return
                    execute(EXPERIMENTS[number - 1])
                analyze(analysis)
    except (EOFError, KeyboardInterrupt):
        print('\nOperation cancelled.')
    except (OSError, ValueError, KeyError) as error:
        print(f'Could not complete the operation: {error}')

