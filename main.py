"""Common entry point for running experiments or analyzing their results."""
from dataclasses import dataclass
from itertools import product
import json
from math import prod
from pathlib import Path

import numpy as np
import pandas as pd
from geopy import distance
from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess
from Read_TSPLIB.raead_distance_matrix_EUC2D_TSPLIB import raead_distance_matrix_EUC2D_TSPLIB
from Read_TSPLIB.raead_distance_matrix_GEO_TSPLIB import raead_distance_matrix_GEO_TSPLIB

ROOT = Path(__file__).resolve().parent


def load_run_options(path=None):
    with Path(path or ROOT / 'run_options.json').open(encoding='utf-8') as stream:
        return json.load(stream)


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
            raise ValueError(f"Dataset desconocido: {values['dataset']}")
        for field in ('steps', 'particles', 'opts', 'minimums', 'maximums',
                      'rings', 'full_tanks'):
            if not isinstance(values[field], list) or not values[field]:
                raise ValueError(f"{field} debe ser una lista no vacía.")
            values[field] = tuple(values[field])
        repetitions = values['repetitions']
        values['repetitions'] = range(repetitions['start'], repetitions['stop'])
        if not values['repetitions']:
            raise ValueError('El rango de repeticiones no puede estar vacío.')
        experiments.append(Experiment(**values))
    return experiments

EXPERIMENTS = build_experiments()


def load_dataset(name):
    dataset = DATASETS[name]
    fmt = dataset['format']
    path = ROOT / 'DataSets' / dataset['filename']
    if fmt == 'euc':
        return np.round(raead_distance_matrix_EUC2D_TSPLIB(path), 0), None
    if fmt == 'matrix':
        return raead_distance_matrix_GEO_TSPLIB(path), None
    if fmt != 'excel':
        raise ValueError(f'Formato de dataset desconocido: {fmt}')
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
    destination = Path(output_dir) if output_dir is not None else ROOT / RUN_OPTIONS['output_dir']
    if experiment.excel:
        destination.mkdir(parents=True, exist_ok=True)
    for index, configuration in enumerate(experiment.configurations(), 1):
        n, c1, opt, minimum, maximum, ring, full, _ = configuration
        print(f'\nEjecución {index}/{experiment.count}: N={n}, c1={c1}, '
              f'Opt={opt}, circuito={ring}, depósito lleno={full}')
        algorithm = ParticleSwarm_VarOptMultiprocess(
            N=n, c1=c1, distance_matrix=matrix, ring_mode=ring,
            refuel_mode=experiment.refuel, prices=prices,
            maxCapacity=experiment.max_capacity, consumption=experiment.consumption, fullinit=full)
        algorithm.run(verbose=DATASETS[experiment.dataset]['verbose'] and not experiment.excel,
                      optType=opt, excel=experiment.excel,
                      file_path=destination / result_filename(experiment, configuration),
                      permutReset=experiment.permut_reset, minPermut=minimum,
                      maxPermut=maximum, k=experiment.k)
        if experiment.dataset == 'bays29' and not experiment.excel:
            print(algorithm.nIter)


def choose_option(title, options, describe):
    print(f'\n{title}')
    for number, option in enumerate(options, 1):
        print(f'{number:2}. {describe(option)}')
    print(' 0. Salir')
    while True:
        try:
            choice = int(input('\nNúmero: '))
        except ValueError:
            print('Introduce un número del menú.')
            continue
        if choice == 0:
            return None
        if 1 <= choice <= len(options):
            return options[choice - 1]
        print('Ese número no aparece en el menú.')


def choose_experiment():
    return choose_option('¿Qué quieres ejecutar?', EXPERIMENTS,
                         lambda experiment: f'{experiment.dataset}: {experiment.label} '
                         f'({experiment.count} ejecuciones)')


def main():
    try:
        mode = choose_option('¿Qué quieres hacer?', ('run', 'analysis'),
                             lambda mode: 'run — Ejecutar' if mode == 'run' else 'analysis — Analizar resultados')
        if mode == 'run':
            experiment = choose_experiment()
            if experiment is not None:
                execute(experiment)
        elif mode == 'analysis':
            from analisis import analyze, load_analysis_options
            analysis = choose_option('¿Qué análisis quieres ejecutar?', load_analysis_options(),
                                     lambda option: option['label'])
            if analysis is not None:
                analyze(analysis)
    except (EOFError, KeyboardInterrupt):
        print('\nOperación cancelada.')
    except (OSError, ValueError, KeyError) as error:
        print(f'No se pudo completar la operación: {error}')


if __name__ == '__main__':
    main()
