"""Sequential CPU adapter and process entry point; no solver semantics live here."""
import json
import re
from pathlib import Path
import sys

from .experiment_batch import (
    DatasetDescriptor, EXPANSION_VERSION, compile_plan, count_runs, iterate_runs,
)
from .experiment_config import ExperimentConfiguration
from .batch_store import (
    start_batch, start_run, finish_run, finish_batch, mark_interrupted,
)


def to_legacy_experiment(run):
    from .runner import Experiment
    e = dict(run.legacy_values)
    return Experiment(
        dataset=run.dataset, label=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', run.legacy_label or run.name), particles=(run.particles,), steps=(run.c1,),
        opts=(run.operator,), minimums=(e['minimum_reset_probability'],),
        maximums=(e['maximum_reset_probability'],), rings=(run.ring,),
        full_tanks=(e['full_initial_tank'],),
        repetitions=range(run.repetition_id, run.repetition_id + 1),
        excel=run.excel, verbose=run.verbose, refuel=run.problem_mode=='tspwr',
        style=run.legacy_style, analysis_output=run.analysis_output,
        max_capacity=e['fuel_capacity'], consumption=e['consumption'],
        permut_reset=run.permutation_reset, k=e['k'],
        reset_threshold_divisor=e['reset_threshold_divisor'],
        primary_operator_share=e['primary_operator_share'],
        progress_warmup_multiplier=e['progress_warmup_multiplier'])


def execute_one(run, output_dir, descriptor):
    from . import runner
    # This adapter runs in the dedicated coordinator process, never a GUI thread.
    original = runner.DATASETS.get(descriptor.id)
    runner.DATASETS[descriptor.id] = dict(filename=descriptor.filename, format=descriptor.format,
                                         source=descriptor.source, problem_types=descriptor.problem_types)
    try:
        return runner.execute(to_legacy_experiment(run), output_dir=output_dir)
    finally:
        if original is None:
            runner.DATASETS.pop(descriptor.id, None)
        else:
            runner.DATASETS[descriptor.id] = original


def execute_batch(directory, run_function=None):
    """Stop on first failure. Re-entrant/resume execution is intentionally rejected."""
    directory = Path(directory)
    with (directory / 'batch.json').open(encoding='utf-8') as stream:
        snapshot = json.load(stream)
    if snapshot['expansion_version'] != EXPANSION_VERSION:
        raise ValueError('Unsupported expansion version')
    config = ExperimentConfiguration.from_dict(snapshot['configuration'])
    catalog = tuple(DatasetDescriptor(**{**d, 'problem_types': tuple(d['problem_types'])}) for d in snapshot['datasets'])
    plan = compile_plan(config, catalog)
    if count_runs(plan) != int(snapshot['total_runs']):
        raise ValueError('Saved run count does not match the configuration')
    descriptors = {d.id: d for d in catalog}
    run_function = execute_one if run_function is None else run_function
    start_batch(directory)
    current = None
    try:
        for ordinal, run in enumerate(iterate_runs(plan), 1):
            current = ordinal
            start_run(directory, ordinal, run)
            destination = directory / 'runs' / str(ordinal)
            # Known before execute() returns, so interrupted artifacts can be found.
            destination.mkdir(parents=True, exist_ok=False)
            output = run_function(run, destination, descriptors[run.dataset])
            finish_run(directory, ordinal, 'succeeded', output=output)
            current = None
        finish_batch(directory, 'succeeded')
    except KeyboardInterrupt:
        mark_interrupted(directory)
    except Exception as error:
        message = f'{type(error).__name__}: {error}'
        if current is not None:
            finish_run(directory, current, 'failed', error=message)
        finish_batch(directory, 'failed', error=message)
    return directory


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m tsp_pso.batch_executor BATCH_DIRECTORY')
    execute_batch(sys.argv[1])


if __name__ == '__main__':
    main()
