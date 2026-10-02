"""Entrada común para las ejecuciones individuales y los experimentos."""
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from geopy import distance
from ParticleSwarm_VarOptMultiprocess import ParticleSwarm_VarOptMultiprocess
from Read_TSPLIB.raead_distance_matrix_EUC2D_TSPLIB import raead_distance_matrix_EUC2D_TSPLIB
from Read_TSPLIB.raead_distance_matrix_GEO_TSPLIB import raead_distance_matrix_GEO_TSPLIB

ROOT = Path(__file__).resolve().parent
# nombre, archivo, formato, c1 individual, mostrar progreso
DATASETS = {
    'berlin52': ('berlin52.tsp', 'euc', 2500, False),
    'bays29': ('bays29.tsp', 'matrix', 1000, False),
    'st70': ('st70.tsp', 'euc', 2000, True),
    'ch150': ('ch150.tsp', 'euc', 8000, True),
    'kroA100': ('kroA100.tsp', 'euc', 3000, True),
    'rat195': ('rat195.tsp', 'euc', 20000, True),
    'Bahia30D': ('ciudades_Bahia30D.xlsx', 'excel', 1200, True),
    'Minas24D': ('Minas24D.xlsx', 'excel', 1200, True),
    'Minas30D': ('Minas30D.xlsx', 'excel', 1500, True),
    'Minas57D': ('Minas57D.xlsx', 'excel', 3000, True),
}


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

    def configurations(self):
        return product(self.particles, self.steps, self.opts, self.minimums,
                       self.maximums, self.rings, self.full_tanks, self.repetitions)

    @property
    def count(self):
        return sum(1 for _ in self.configurations())


def build_experiments():
    experiments = [Experiment(name, 'individual', (c1,), rings=(fmt != 'excel',),
                              full_tanks=(fmt == 'excel',))
                   for name, (_, fmt, c1, _) in DATASETS.items()]
    experiments.extend([
        Experiment('berlin52', 'barrido de c1 y probabilidades', (1000, 2000, 5000),
                   minimums=(0.0, 0.2, 0.4), maximums=(0.4, 0.6, 0.8),
                   repetitions=range(1, 11), excel=True, style='berlin_grid'),
        Experiment('berlin52', 'Opt 21', (2000, 2200, 2400, 2600, 2800, 3000),
                   opts=(21,), repetitions=range(1, 31), excel=True),
        Experiment('bays29', 'barrido de partículas', (2000,),
                   particles=(2, 4, 6, 8, 10, 12, 14, 16),
                   repetitions=range(1, 11), excel=True, style='bays'),
        Experiment('st70', 'barrido de c1', (3400, 3600, 3800, 4000),
                   repetitions=range(1, 31), excel=True),
        Experiment('ch150', 'barrido de c1', (6000, 7000, 8000, 9000, 10000),
                   repetitions=range(1, 11), excel=True),
        Experiment('kroA100', 'repeticiones 17–20', (3600,), particles=(16,),
                   repetitions=range(17, 21), excel=True),
        Experiment('rat195', 'repeticiones 6–10', (20000,),
                   repetitions=range(6, 11), excel=True),
    ])
    experiments.extend(Experiment(name, 'circuito y depósito inicial', (c1,),
                                  rings=(False, True), full_tanks=(False, True),
                                  repetitions=range(1, 31), excel=True,
                                  refuel=True, style='fuel')
                       for name, (_, fmt, c1, _) in DATASETS.items() if fmt == 'excel')
    return experiments


EXPERIMENTS = build_experiments()


def load_dataset(name):
    filename, fmt, _, _ = DATASETS[name]
    path = ROOT / 'DataSets' / filename
    if fmt == 'euc':
        return np.round(raead_distance_matrix_EUC2D_TSPLIB(path), 0), None
    if fmt == 'matrix':
        return raead_distance_matrix_GEO_TSPLIB(path), None
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
        suffix = f'10_{number}_{minimum}_{maximum}'
    else:
        suffix = f'10_{minimum}_{maximum}_{number}'
    return f'{prefix}_{suffix}.xlsx'


def execute(experiment, output_dir=None):
    matrix, prices = load_dataset(experiment.dataset)
    destination = Path(output_dir) if output_dir is not None else ROOT / 'Resultados'
    if experiment.excel:
        destination.mkdir(parents=True, exist_ok=True)
    for index, configuration in enumerate(experiment.configurations(), 1):
        n, c1, opt, minimum, maximum, ring, full, _ = configuration
        print(f'\nEjecución {index}/{experiment.count}: N={n}, c1={c1}, '
              f'Opt={opt}, circuito={ring}, depósito lleno={full}')
        algorithm = ParticleSwarm_VarOptMultiprocess(
            N=n, c1=c1, distance_matrix=matrix, ring_mode=ring,
            refuel_mode=experiment.refuel, prices=prices,
            maxCapacity=150.0, consumption=7.0, fullinit=full)
        algorithm.run(verbose=DATASETS[experiment.dataset][3] and not experiment.excel,
                      optType=opt, excel=experiment.excel,
                      file_path=destination / result_filename(experiment, configuration),
                      permutReset=True, minPermut=minimum, maxPermut=maximum, k=10)
        if experiment.dataset == 'bays29' and not experiment.excel:
            print(algorithm.nIter)


def choose_experiment():
    print('\n¿Qué quieres ejecutar?')
    for number, experiment in enumerate(EXPERIMENTS, 1):
        print(f'{number:2}. {experiment.dataset}: {experiment.label} '
              f'({experiment.count} ejecuciones)')
    print(' 0. Salir')
    while True:
        try:
            choice = int(input('\nNúmero: '))
        except ValueError:
            print('Introduce un número del menú.')
            continue
        if choice == 0:
            return None
        if 1 <= choice <= len(EXPERIMENTS):
            return EXPERIMENTS[choice - 1]
        print('Ese número no aparece en el menú.')


def main():
    try:
        experiment = choose_experiment()
        if experiment is not None:
            execute(experiment)
    except (EOFError, KeyboardInterrupt):
        print('\nEjecución cancelada.')


if __name__ == '__main__':
    main()
