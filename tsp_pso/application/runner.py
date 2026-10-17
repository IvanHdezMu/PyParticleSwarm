"""Configure, run, and select TSP particle swarm experiments."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ..algorithms.solver_registry import SOLVER_REGISTRY
from ..algorithms.core.pso_config import PSOConfig
from ..experiments.experiment import Experiment, build_experiments as _build_experiments
# Re-export these helpers for callers using the existing runner API.
from ..experiments.result_naming import extra_filename_fields, result_filename
# Re-export the configuration reader for existing callers.
from ..infrastructure.experiment_options import load_run_options
from ..infrastructure.dataset_reader import load_dataset as _load_dataset

ROOT = Path(__file__).resolve().parents[2]


RUN_OPTIONS = load_run_options()
DATASETS = RUN_OPTIONS['datasets']

def build_experiments(options=None):
    """Compatibility wrapper using RUN_OPTIONS when options are omitted or None."""
    return _build_experiments(RUN_OPTIONS if options is None else options)


EXPERIMENTS = build_experiments()


def load_dataset(name):
    """Read a named dataset from the current catalog using the project dataset root."""
    return _load_dataset(DATASETS[name], ROOT / 'datasets')


def create_run_directory(experiment, output_dir=None):
    """Reserve a unique execution directory and save its effective configuration."""
    created_at = datetime.now(timezone.utc).replace(microsecond=0)

    def compact(values):
        values = tuple(values)
        text = '-'.join(map(str, values)) if len(values) <= 2 else f'{values[0]}-{values[-1]}x{len(values)}'
        return re.sub(r'[^A-Za-z0-9.-]', '-', text)[:24]

    summary = '_'.join(f'{name}{compact(values)}' for name, values in (
        ('N', experiment.particles), ('c1', experiment.steps), ('opt', experiment.opts),
        ('ring', experiment.rings), ('full', experiment.full_tanks),
        ('k', (experiment.k,)), ('min', experiment.minimums), ('max', experiment.maximums),
    ))
    parent = (Path(output_dir) if output_dir is not None
              else ROOT / RUN_OPTIONS['output_dir']) / experiment.dataset
    parent.mkdir(parents=True, exist_ok=True)
    stem = f'{created_at:%Y-%m-%d_%H-%M-%S}_{summary}'
    attempt = 1
    while True:
        destination = parent / (stem if attempt == 1 else f'{stem}__{attempt}')
        try:
            destination.mkdir()
            break
        except FileExistsError:
            attempt += 1
    configuration = asdict(experiment)
    configuration['repetitions'] = {'start': experiment.repetitions.start,
                                    'stop': experiment.repetitions.stop,
                                    'step': experiment.repetitions.step}
    configuration['created_at'] = created_at.isoformat()
    with (destination / 'run_config.json').open('x', encoding='utf-8') as stream:
        json.dump(configuration, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return destination


def execute(experiment, output_dir=None, *, problem_type=None):
    """Run a registered problem, defaulting to the legacy refuel configuration."""
    if problem_type is None:
        problem_type = 'tspwr' if experiment.refuel else 'tsp'
    solver_class, problem_arguments = SOLVER_REGISTRY[problem_type]
    matrix, prices = load_dataset(experiment.dataset)
    if experiment.excel:
        filenames = [result_filename(experiment, c) for c in experiment.configurations()]
        if len(filenames) != len(set(filenames)):
            raise ValueError('Experiment contains duplicate result filenames')
    destination = create_run_directory(experiment, output_dir)
    for index, configuration in enumerate(experiment.configurations(), 1):
        n, c1, opt, minimum, maximum, ring, full, _ = configuration
        print(f'\nRun {index}/{experiment.count}: N={n}, c1={c1}, '
              f'Opt={opt}, circuit={ring}, full tank={full}')
        algorithm = solver_class(
            matrix=matrix,
            config=PSOConfig(
                N=n, c1=c1, ring_mode=ring,
                reset_threshold_divisor=experiment.reset_threshold_divisor,
                primary_operator_share=experiment.primary_operator_share,
                progress_warmup_multiplier=experiment.progress_warmup_multiplier),
            **problem_arguments(experiment, prices, full))
        algorithm.run(verbose=experiment.verbose,
                      optType=opt, excel=experiment.excel,
                      file_path=destination / result_filename(experiment, configuration),
                      permutReset=experiment.permut_reset, minPermut=minimum,
                      maxPermut=maximum, k=experiment.k)
    return destination

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
            from ..analysis.analysis import analyze, first_missing_result, load_analysis_options
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

