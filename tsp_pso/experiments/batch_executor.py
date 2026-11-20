"""Sequential CPU adapter and process entry point; no solver semantics live here."""
from pathlib import Path
import sys

from ..application import runner
from .batch_store import (
    finish_batch, finish_run, mark_interrupted, start_batch, start_run, read_batch,
)
from .experiment_batch import (
    iterate_runs,
)


def execute_one(run, output_dir, descriptor):
    """Execute a run with its snapshot's dataset descriptor and return its directory.

    Forward output_dir without rebasing it and propagate execution errors. No
    live catalog is read or temporarily modified by this adapter.
    """
    dataset = dict(filename=descriptor.filename, format=descriptor.format,
                   source=descriptor.source, problem_types=descriptor.problem_types)
    return runner.execute(run, output_dir=output_dir, dataset=dataset)


def execute_batch(directory, run_function=None):
    """Execute a saved batch sequentially and return its directory as a Path.

    Validate the snapshot version and expanded count before starting. An optional
    run_function(run, output_dir, descriptor) must return the execution directory.
    Record the first execution failure or interruption and stop; setup errors
    propagate. Re-entrant/resume execution is intentionally rejected. After success,
    generate the summary; analysis errors are logged separately from run status.
    """
    directory = Path(directory)
    plan, batch, runs = read_batch(directory)
    if batch['status'] != 'pending':
        raise ValueError('Only a new pending batch may be started; resume is not implemented')
    if runs or any(batch[name] is not None for name in ('started_at', 'ended_at', 'error')):
        raise ValueError('Inconsistent pending batch: existing runs or execution metadata')
    descriptors = {d.id: d for d in plan.datasets}
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
    else:
        try:
            from ..analysis.analysis import analyze_batch
            analyze_batch(directory)
        except (Exception, KeyboardInterrupt) as error:
            message = f'Batch succeeded; analysis failed: {type(error).__name__}: {error}'
            # The coordinator may already redirect these streams to execution.log.
            # Flush before appending so buffered execution output is not overwritten.
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                with (directory / 'execution.log').open('a', encoding='utf-8') as log:
                    log.write(message + '\n')
            except OSError as log_error:
                print(f'{message}; cannot write execution.log: {log_error}', file=sys.stderr)
    return directory


def main():
    """Execute the batch directory supplied as the sole command-line argument."""
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m tsp_pso.experiments.batch_executor BATCH_DIRECTORY')
    execute_batch(sys.argv[1])


if __name__ == '__main__':
    main()
