"""Coordinate experiment execution with explicit inputs and on-demand defaults."""
from pathlib import Path

from ..algorithms.core.pso_config import PSOConfig
from ..algorithms.solver_registry import SOLVER_REGISTRY
# Experiment also preserves unpickling of instances saved under the runner module.
from ..experiments.experiment import Experiment, build_experiments as _build_experiments
# Keep the public filename helpers and configuration reader available to old callers.
from ..experiments.result_naming import extra_filename_fields, result_filename
from ..infrastructure.dataset_reader import load_dataset as _load_dataset
from ..infrastructure.experiment_options import load_run_options
from ..infrastructure.run_storage import create_run_directory as _create_run_directory

ROOT = Path(__file__).resolve().parents[2]


def build_experiments(options=None):
    """Compatibility entry point; load default options only when called without them."""
    return _build_experiments(load_run_options() if options is None else options)


def load_dataset(name, *, datasets=None, datasets_root=None):
    """Return (distance matrix, prices) for a named catalog entry.

    Omitted datasets are loaded from the default configuration. Relative dataset
    filenames use datasets_root, or the project's datasets directory by default;
    absolute filenames are preserved. Unknown names raise KeyError and reader
    errors propagate unchanged.
    """
    if datasets is None:
        datasets = load_run_options()['datasets']
    return _load_dataset(datasets[name], ROOT / 'datasets' if datasets_root is None else datasets_root)


def create_run_directory(experiment, output_dir=None, *, run_options=None):
    """Return the reserved run directory after saving its configuration snapshot.

    An explicit output_dir is used as supplied, relative to the working directory
    when applicable. Otherwise resolve run_options['output_dir'] from ROOT,
    loading default options only when needed. Storage errors propagate unchanged.
    """
    if output_dir is None:
        options = load_run_options() if run_options is None else run_options
        output_dir = ROOT / options['output_dir']
    return _create_run_directory(experiment, output_dir)


def execute(experiment, output_dir=None, *, problem_type=None, dataset=None,
            run_options=None, datasets_root=None):
    """Coordinate a run with an optional dataset descriptor and experiment options.

    Explicit dataset/output paths avoid loading default configuration. Missing
    values use options loaded on demand, preserving project-relative defaults
    and working-directory-relative explicit output paths. dataset is a mapping
    with filename and format; it takes precedence over run_options['datasets'].
    datasets_root defaults to ROOT/datasets. problem_type overrides the selection
    based on experiment.refuel.

    Return the reserved run directory. Duplicate Excel filenames raise ValueError
    before storage is created; reader, storage and solver errors propagate. Once
    created, snapshots and partial results remain available after a solver error.
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
    # terminal imports runner; defer this reverse dependency until invocation.
    from ..presentation.terminal import main as terminal_main
    return terminal_main()
