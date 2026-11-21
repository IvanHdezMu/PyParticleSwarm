"""Analyze explicit groups of Excel histories and completed batches."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path, PureWindowsPath
from zipfile import BadZipFile

import pandas as pd

from ..experiments.batch_store import positive_decimal, read_batch
from ..experiments.experiment_batch import (
    CONDITIONAL,
    validate_run_configuration,
)
from ..experiments.experiment_batch import (
    RUN_AXES as _BATCH_AXES,
)
from ..experiments.result_naming import result_filename

# ROOT: Project root directory used as the default base path
# when locating and analyzing experiment results.
ROOT = Path(__file__).resolve().parents[2]
# METRICS: Names of the analysis metrics, in the same order as their calculated values.
METRICS = ['mean_minimum_result', 'mean_step_of_minimum', 'best_result']


def _history_minimum(frame):
    """Return the first sampled minimum and its Step without changing the frame."""
    if not {'Result', 'Step'}.issubset(frame.columns):
        raise ValueError('missing Result or Step columns.')
    if frame.empty or frame['Result'].isna().all():
        raise ValueError('does not contain valid results.')
    index = frame['Result'].idxmin()
    minimum = frame.loc[index, 'Result']
    step = frame.loc[index, 'Step']
    if pd.isna(step):
        raise ValueError('the minimum result has no Step.')
    return minimum, step


def analyze(analysis, root=None, *, groups, announce=True):
    """Summarize ordered (parameter_mapping, excel_paths) groups and save Excel.

    Relative paths use root, or the project directory when omitted. Each path
    iterable must be nonempty. Groups and histories retain their supplied order.
    The definition supplies columns and output; output=None skips writing.
    announce=False suppresses the save notice until a caller publishes its
    temporary output. Return a DataFrame, empty when the group iterable is empty.
    """
    base = Path(root) if root is not None else ROOT
    rows = []
    for configuration, excel_paths in groups:
        minimums, steps, paths = [], [], []
        for path in excel_paths:
            path = base / path
            try:
                frame = pd.read_excel(path)
            except FileNotFoundError as error:
                raise FileNotFoundError(f'Missing results file: {path}') from error
            except (OSError, ValueError, KeyError, TypeError, BadZipFile) as error:
                raise ValueError(f'{path}: {error}') from error
            try:
                minimum, step = _history_minimum(frame)
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f'{path}: {error}') from error
            minimums.append(minimum)
            steps.append(step)
            paths.append(path)
        if not minimums:
            raise ValueError(f'The repetition paths cannot be empty: {configuration}')
        row = {column: configuration[column] for column in analysis['columns']}
        try:
            row.update(zip(METRICS, (sum(minimums) / len(minimums),
                                    sum(steps) / len(steps), min(minimums))))
        except (ValueError, TypeError) as error:
            inputs = '; '.join(f'{path} (minimum={minimum!r}, Step={step!r})'
                               for path, minimum, step in zip(paths, minimums, steps))
            raise ValueError(f'Cannot aggregate histories: {inputs}: {error}') from error
        rows.append(row)
    table = pd.DataFrame(rows, columns=analysis['columns'] + METRICS)
    if analysis['output'] is not None:
        destination = base / analysis['output']
        destination.parent.mkdir(parents=True, exist_ok=True)
        table.to_excel(destination, index=False)
        if announce:
            print(f'Analysis saved to {destination}')
    print(table.to_string(index=False))
    return table


_BATCH_KEY_FIELDS = (*_BATCH_AXES, *CONDITIONAL, 'verbose', 'excel')
# Parameter columns only; analyze() appends the unchanged METRICS.
BATCH_COLUMNS = [
    'dataset', 'problem_mode', 'particles', 'c1', 'operator', 'ring',
    'permutation_reset', 'k', 'primary_operator_share',
    'minimum_reset_probability', 'maximum_reset_probability',
    'reset_threshold_divisor', 'progress_warmup_multiplier', 'fuel_capacity',
    'consumption', 'full_initial_tank', 'repetitions', 'inactive_parameters',
]


def _batch_json(path):
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def _batch_same_value(actual, expected):
    """Use numeric equality without accepting booleans in place of numbers."""
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(_batch_same_value(actual[k], v) for k, v in expected.items()))
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(_batch_same_value(a, e) for a, e in zip(actual, expected)))
    return (isinstance(actual, bool) == isinstance(expected, bool)
            and actual == expected)


def _batch_load_batch(directory):
    plan, batch, runs = read_batch(directory)
    configuration = plan.configuration
    total = positive_decimal(batch['total'])
    identifier = batch['id']
    if len(configuration.datasets) != 1 or len(configuration.problem_modes) != 1:
        raise ValueError('Batch analysis requires exactly one dataset and one problem mode')
    if not configuration.excel:
        raise ValueError('Batch has excel=False; no histories are available')
    if batch['status'] != 'succeeded':
        raise ValueError(f"Batch status is {batch['status']!r}; expected succeeded")
    if not batch['started_at'] or not batch['ended_at'] or batch['error'] is not None:
        raise ValueError('Inconsistent batch completion record')
    if len(runs) != total:
        raise ValueError(f'Incomplete batch: expected {total} runs, found {len(runs)}')
    runs.sort(key=lambda row: positive_decimal(row['ordinal']))
    for ordinal, row in enumerate(runs, 1):
        if positive_decimal(row['ordinal']) != ordinal:
            raise ValueError(f'Missing, duplicate or inconsistent ordinal at run {ordinal}')
        if row['run_id'] != f'{identifier}-{ordinal}':
            raise ValueError(f'Run {ordinal}: inconsistent run_id')
    return configuration, runs


def _batch_configuration(run, requested):
    values = validate_run_configuration(run, requested)
    if not run['excel']:
        raise ValueError('Run has excel=False')
    return values


def _batch_result_path(directory, record, run):
    ordinal, dataset = record['ordinal'], run['dataset']
    output = record['output']
    if not isinstance(output, str) or not output:
        raise ValueError('Missing output directory')
    # Use only the recorded layout suffix: absolute roots can belong to another
    # machine, and the selected batch may have been moved or copied.
    parts = PureWindowsPath(output).parts
    if (len(parts) < 4 or parts[-4:-1] != ('runs', ordinal, dataset)
            or dataset in ('.', '..') or '/' in dataset or '\\' in dataset
            or parts[-1] in ('.', '..')):
        raise ValueError('Output does not match ordinal/dataset layout')
    destination = directory / 'runs' / ordinal / dataset / parts[-1]
    saved = _batch_json(destination / 'run_config.json')
    datetime.fromisoformat(saved['created_at'])
    if not isinstance(saved['label'], str) or not saved['label'].strip():
        raise ValueError(f'{destination}/run_config.json: invalid label')
    e = run['legacy_values']
    expected = {
        'dataset': dataset, 'steps': [run['c1']], 'particles': [run['particles']],
        'opts': [run['operator']], 'minimums': [e['minimum_reset_probability']],
        'maximums': [e['maximum_reset_probability']], 'rings': [run['ring']],
        'full_tanks': [e['full_initial_tank']],
        'repetitions': {'start': run['repetition_id'], 'stop': run['repetition_id'] + 1, 'step': 1},
        'excel': run['excel'], 'verbose': run['verbose'],
        'refuel': run['problem_mode'] == 'tspwr', 'style': run['legacy_style'],
        'max_capacity': e['fuel_capacity'], 'consumption': e['consumption'],
        'permut_reset': run['permutation_reset'], 'k': e['k'],
        'reset_threshold_divisor': e['reset_threshold_divisor'],
        'primary_operator_share': e['primary_operator_share'],
        'progress_warmup_multiplier': e['progress_warmup_multiplier'],
        'analysis_output': run['analysis_output'],
    }
    for name, value in expected.items():
        if not _batch_same_value(saved[name], value):
            raise ValueError(f'{destination}/run_config.json: inconsistent {name}')
    configuration = (run['particles'], run['c1'], run['operator'],
                     e['minimum_reset_probability'], e['maximum_reset_probability'],
                     run['ring'], e['full_initial_tank'], run['repetition_id'])
    path = destination / result_filename(saved['dataset'], saved['style'], saved['k'], configuration)
    if not path.is_file():
        raise ValueError(f'Missing result history: {path}')
    return path


def prepare_batch_groups(directory):
    """Prepare (parameters, ordered Excel paths) pairs for the original analyze().

    Read a complete single-dataset, single-problem batch using its saved catalog,
    configuration and read-only manifest. Validate all repetitions and snapshots;
    resolve histories below the selected directory even if the batch was moved.
    Group by persisted effective scalars, retaining first-ordinal group order and
    ascending repetition IDs. No datasets, solvers or Excel histories are loaded,
    no defaults are recomputed and no files are written. History contents are
    validated by analyze(), not by this preparation step. Invalid batch metadata
    or missing artifacts raise a contextual ValueError; no partial groups return.
    """
    directory = Path(directory).resolve()
    try:
        requested, records = _batch_load_batch(directory)
        spec = requested.repetitions
        groups = {}
        expanded_keys = {}
        for record in records:
            ordinal = record['ordinal']
            try:
                if record['status'] != 'succeeded':
                    raise ValueError(f"Run status is {record['status']!r}; expected succeeded")
                if not record['started_at'] or not record['ended_at'] or record['error'] is not None:
                    raise ValueError('Inconsistent run completion record')
                run = json.loads(record['configuration'])
                row = _batch_configuration(run, requested)
                repetition = run['repetition_id']
                if not spec.first_id <= repetition < spec.first_id + spec.count:
                    raise ValueError(f'Unexpected repetition_id: {repetition}')
                key = tuple(row[name] for name in _BATCH_KEY_FIELDS)
                expanded = tuple(run[name] for name in _BATCH_KEY_FIELDS)
                if expanded in expanded_keys and expanded_keys[expanded] != key:
                    raise ValueError('Inconsistent effective values for the same expanded configuration')
                expanded_keys[expanded] = key
                if key not in groups:
                    groups[key] = (row, {})
                members = groups[key][1]
                if repetition in members:
                    raise ValueError(f'Duplicate repetition_id: {repetition}')
                members[repetition] = (ordinal, _batch_result_path(directory, record, run))
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                raise ValueError(f'Run {ordinal}: {error}') from error
        for row, members in groups.values():
            if len(members) != spec.count:
                raise ValueError(
                    f'Incomplete repetitions for {row}: expected {spec.count}, found {len(members)}')
        prepared = []
        for row, members in groups.values():
            row['repetitions'] = spec.count
            parameters = {name: row[name] for name in BATCH_COLUMNS}
            paths = [members[repetition][1] for repetition in sorted(members)]
            prepared.append((parameters, paths))
        return prepared
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError(f'Batch {directory}: {error}') from error


def analyze_batch(directory):
    """Publish Analysis.xlsx for a complete, single-dataset/problem batch.

    Use the original analyzer for all reading, statistics and workbook writing.
    Return the published Path; any failure leaves an existing summary intact.
    """
    from tempfile import TemporaryDirectory
    from openpyxl import load_workbook

    directory = Path(directory).resolve()
    groups = prepare_batch_groups(directory)
    destination = directory / 'Analysis.xlsx'
    with TemporaryDirectory(prefix='.analysis-', dir=directory) as temporary:
        output = Path(temporary) / 'Analysis.xlsx'
        analyze({'columns': BATCH_COLUMNS, 'output': output}, groups=groups, announce=False)
        workbook = load_workbook(output)
        try:
            sheet = workbook.active
            sheet.title = 'Analysis'
            sheet.auto_filter.ref = sheet.dimensions
            sheet.freeze_panes = 'A2'
            workbook.save(output)
        finally:
            workbook.close()
        output.replace(destination)
    print(f'Analysis saved to {destination}')
    return destination
