"""Coordinate concrete run execution with explicit dataset inputs."""
from pathlib import Path

from ..algorithms.core.pso_config import PSOConfig
from ..algorithms.solver_registry import SOLVER_REGISTRY
from ..experiments.result_naming import result_filename
from ..infrastructure.dataset_reader import load_dataset as _load_dataset
from ..infrastructure.run_storage import create_run_directory as _create_run_directory

# ROOT: Project root directory used to resolve default dataset and output paths.
ROOT = Path(__file__).resolve().parents[2]


def execute(run, output_dir=None, *, dataset, datasets_root=None):
    """Execute one ConcreteRunConfiguration using its persisted effective scalars.

    The dataset descriptor is explicit. An omitted output directory uses the
    concrete configuration, relative to ROOT; explicit paths keep their meaning.
    Return the reserved directory; snapshots survive solver failures. Historical
    Experiment inputs are deliberately not an execution API.
    """
    solver_class, problem_arguments = SOLVER_REGISTRY[run.problem_mode]
    values = dict(run.legacy_values)
    if output_dir is None:
        output_dir = ROOT / run.output_dir
    matrix, prices = _load_dataset(dataset, ROOT / 'datasets' if datasets_root is None else datasets_root)
    configuration = (run.particles, run.c1, run.operator,
                     values['minimum_reset_probability'], values['maximum_reset_probability'],
                     run.ring, values['full_initial_tank'], run.repetition_id)
    filename = result_filename(run.dataset, run.legacy_style, values['k'], configuration)
    destination = _create_run_directory(run, output_dir, values)
    print(f"\nRun 1/1: N={run.particles}, c1={run.c1}, Opt={run.operator}, "
          f"circuit={run.ring}, full tank={values['full_initial_tank']}")
    algorithm = solver_class(
        matrix=matrix,
        config=PSOConfig(N=run.particles, c1=run.c1, ring_mode=run.ring,
                         reset_threshold_divisor=values['reset_threshold_divisor'],
                         primary_operator_share=values['primary_operator_share'],
                         progress_warmup_multiplier=values['progress_warmup_multiplier']),
        **problem_arguments(prices, values['full_initial_tank'],
                            values['fuel_capacity'], values['consumption']))
    algorithm.run(verbose=run.verbose, optType=run.operator, excel=run.excel,
                  file_path=destination / filename, permutReset=run.permutation_reset,
                  minPermut=values['minimum_reset_probability'],
                  maxPermut=values['maximum_reset_probability'], k=values['k'])
    return destination
