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


def build_experiments(options=None):
    """Compatibility entry point; load default options only when called without them."""
    return _build_experiments(load_run_options() if options is None else options)


def load_dataset(name, *, datasets=None, datasets_root=None):
    """Read from an explicit catalog, or load the default catalog on demand."""
    if datasets is None:
        datasets = load_run_options()['datasets']
    return _load_dataset(datasets[name], ROOT / 'datasets' if datasets_root is None else datasets_root)


def create_run_directory(experiment, output_dir=None, *, run_options=None):
    """Use an explicit output path or the configured project-relative default."""
    if output_dir is None:
        options = load_run_options() if run_options is None else run_options
        output_dir = ROOT / options['output_dir']
    return _create_run_directory(experiment, output_dir)


def execute(experiment, output_dir=None, *, problem_type=None, dataset=None,
            run_options=None, datasets_root=None):
    """Coordinate a run with an optional dataset descriptor and experiment options.

    Explicit dataset/output paths avoid loading default configuration. Missing
    values use options loaded on demand, preserving project-relative defaults
    and working-directory-relative explicit output paths.
    """
    if problem_type is None:
        problem_type = 'tspwr' if experiment.refuel else 'tsp'
    solver_class, problem_arguments = SOLVER_REGISTRY[problem_type]
    if run_options is None and (dataset is None or output_dir is None):
        run_options = load_run_options()
    if dataset is None:
        dataset = run_options['datasets'][experiment.dataset]
    matrix, prices = _load_dataset(dataset, ROOT / 'datasets' if datasets_root is None else datasets_root)
    if experiment.excel:
        filenames = [result_filename(experiment, c) for c in experiment.configurations()]
        if len(filenames) != len(set(filenames)):
            raise ValueError('Experiment contains duplicate result filenames')
    destination = create_run_directory(experiment, output_dir, run_options=run_options)
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
    # Keep presentation out of application imports until the compatibility entry is called.
    from ..presentation.terminal import main as terminal_main
    return terminal_main()
