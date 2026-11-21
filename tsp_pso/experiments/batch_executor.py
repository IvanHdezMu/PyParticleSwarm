"""Sequential CPU adapter and process entry point; no solver semantics live here."""
from pathlib import Path
import sys
import json
import os

from ..application import runner
from .batch_store import (
    finish_batch, finish_run, mark_interrupted, start_batch, start_run, read_batch,
)
from .experiment_batch import (
    ConcreteRunConfiguration,
)


def execute_one(run, output_dir, descriptor):
    """Execute a run with its snapshot's dataset descriptor and return its directory.

    Forward output_dir without rebasing it and propagate execution errors. No
    live catalog is read or temporarily modified by this adapter.
    """
    dataset = dict(filename=descriptor.filename, format=descriptor.format,
                   source=descriptor.source, problem_types=descriptor.problem_types)
    return runner.execute(run, output_dir=output_dir, dataset=dataset)


def execute_batch(directory, run_function=None, *, _process_group=False):
    """Execute a saved batch sequentially and return its directory as a Path.

    Validate the snapshot and persisted queue before starting. An optional
    run_function(run, output_dir, descriptor) must return the execution directory.
    Record the first execution failure or interruption and stop; setup errors
    propagate. Resume skips confirmed runs and retries interrupted runs. After success,
    generate the summary; analysis errors are logged separately from run status.
    """
    directory = Path(directory).resolve()
    plan, batch, runs = read_batch(directory)
    from .experiment_process import execution_lock
    with execution_lock(directory, retain_owner=_process_group):
        # Re-read after acquiring ownership: another coordinator may have finished.
        plan, batch, runs = read_batch(directory)
        if batch['status'] == 'succeeded':
            raise ValueError('Completed batch cannot resume; results are preserved')
        if batch['status'] == 'running':
            mark_interrupted(directory, 'Previous coordinator exited; restarting unfinished run')
            plan, batch, runs = read_batch(directory)
        if batch['status'] not in ('pending','paused','interrupted'):
            raise ValueError(f"Batch cannot resume from {batch['status']}")
        return _execute_saved(directory, plan, runs, execute_one if run_function is None else run_function)


def _execute_saved(directory, plan, runs, run_function):
    descriptors = {d.id: d for d in plan.datasets}
    start_batch(directory)
    current = None
    try:
        for record in runs:
            if record['status'] == 'succeeded':
                continue
            if record['status'] not in ('pending','interrupted'):
                raise ValueError(f"Cannot execute run in state {record['status']}")
            ordinal = int(record['ordinal'])
            run = ConcreteRunConfiguration.from_dict(json.loads(record['configuration']))
            current = ordinal
            if not start_run(directory, ordinal, run):
                return directory
            destination = directory / 'runs' / str(ordinal)
            # Known before execute() returns, so interrupted artifacts can be found.
            destination.mkdir(parents=True, exist_ok=True)
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
    if os.name == 'posix' and os.getpgrp() != os.getpid():
        os.setsid()
    execute_batch(sys.argv[1], _process_group=True)


if __name__ == '__main__':
    main()
