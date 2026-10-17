"""Configure, run, and select TSP particle swarm experiments."""
from pathlib import Path

from ..algorithms.solver_registry import SOLVER_REGISTRY
from ..algorithms.core.pso_config import PSOConfig
from ..experiments.experiment import Experiment, build_experiments as _build_experiments
# Re-export these helpers for callers using the existing runner API.
from ..experiments.result_naming import extra_filename_fields, result_filename
# Re-export the configuration reader for existing callers.
from ..infrastructure.experiment_options import load_run_options
from ..infrastructure.dataset_reader import load_dataset as _load_dataset
from ..infrastructure.run_storage import create_run_directory as _create_run_directory

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
    """Reserve storage using the configured project root unless a path is supplied."""
    output_dir = Path(output_dir) if output_dir is not None else ROOT / RUN_OPTIONS['output_dir']
    return _create_run_directory(experiment, output_dir)


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

def main():
    """Compatibility entry point for the terminal interface."""
    # Import on invocation: terminal uses this module's current experiment catalog.
    from ..presentation.terminal import main as terminal_main
    return terminal_main()
