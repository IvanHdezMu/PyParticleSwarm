"""Analyze results using experiments defined in config/experiments.json."""
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METRICS = ['mean_minimum_result', 'mean_step_of_minimum', 'best_result']


def analysis_for_experiment(analysis, options):
    """Resolve a run reference using the same configurations and names as execute."""
    from .runner import build_experiments, result_filename

    reference = analysis['experiment']
    matches = [experiment for experiment in build_experiments(options)
               if experiment.dataset == reference['dataset']
               and experiment.label == reference['label']]
    if len(matches) != 1:
        raise ValueError(f"{analysis['id']}: the analysis must match exactly one run.")
    experiment = matches[0]
    if not experiment.excel:
        raise ValueError(f"{analysis['id']}: the run does not save results (excel=false).")
    parameters = {'random': [True], 'N': list(experiment.particles),
                  'c1': list(experiment.steps), 'optType': list(experiment.opts)}
    if experiment.style == 'fuel':
        parameters.update(ring=list(experiment.rings), full=list(experiment.full_tanks))
    elif experiment.style != 'bays':
        parameters.update(kv=[experiment.k], minR=list(experiment.minimums),
                          maxR=list(experiment.maximums))
    filename = result_filename(experiment, ('{N}', '{c1}', '{optType}',
                              '{minR}', '{maxR}', '{ring}', '{full}', '{number}'))
    destination = Path(options['output_dir']) / experiment.dataset
    return {**analysis, 'parameters': parameters, 'columns': list(parameters),
            'repetitions': {'start': experiment.repetitions.start,
                            'stop': experiment.repetitions.stop},
            'input_template': str(destination / filename),
            'output': str(destination / analysis['output']) if analysis['output'] else None}


def load_analysis_options(run_options_path=None):
    from .runner import build_experiments, load_run_options

    options = load_run_options(run_options_path)
    analyses = list(options.get('historical_analyses', []))
    for experiment in build_experiments(options):
        analysis = {
            'id': f'{experiment.dataset}_{experiment.label}',
            'label': f'{experiment.dataset}: {experiment.label}',
            'experiment': {'dataset': experiment.dataset, 'label': experiment.label},
            'output': experiment.analysis_output or
                      f'Analysis_{experiment.dataset}_{experiment.label}.xlsx',
        }
        analyses.append(analysis_for_experiment(analysis, options))
    identifiers = set()
    for analysis in analyses:
        if analysis['id'] in identifiers:
            raise ValueError(f"Duplicate analysis identifier: {analysis['id']}")
        identifiers.add(analysis['id'])
        parameters = analysis['parameters']
        if not parameters or any(not isinstance(v, list) or not v for v in parameters.values()):
            raise ValueError(f"Empty or invalid parameters in {analysis['id']}.")
        if any(column not in parameters for column in analysis['columns']):
            raise ValueError(f"Unknown columns in {analysis['id']}.")
        if not repetition_numbers(analysis):
            raise ValueError(f"Empty repetitions in {analysis['id']}.")
    return analyses


def repetition_numbers(analysis):
    repetitions = analysis['repetitions']
    return range(repetitions['start'], repetitions['stop'])


def first_missing_result(analysis, root=None):
    base = Path(root) if root is not None else ROOT
    parameters = analysis['parameters']
    for values in product(*parameters.values()):
        configuration = dict(zip(parameters, values))
        for number in repetition_numbers(analysis):
            path = base / analysis['input_template'].format(**configuration, number=number)
            if not path.is_file():
                return path
    return None


def analyze(analysis, root=None):
    """Group minimum results and steps by configuration and save the completed table.

    Relative paths are resolved from the project directory. A missing or invalid
    file stops the analysis to avoid publishing averages from incomplete data.
    """
    base = Path(root) if root is not None else ROOT
    parameters = analysis['parameters']
    rows = []
    numbers = repetition_numbers(analysis)
    if not numbers:
        raise ValueError('The repetition range cannot be empty.')
    for values in product(*parameters.values()):
        configuration = dict(zip(parameters, values))
        minimums, steps = [], []
        for number in numbers:
            path = base / analysis['input_template'].format(**configuration, number=number)
            try:
                frame = pd.read_excel(path)
            except FileNotFoundError as error:
                raise FileNotFoundError(f'Missing results file: {path}') from error
            if not {'Result', 'Step'}.issubset(frame.columns):
                raise ValueError(f'{path}: missing Result or Step columns.')
            if frame.empty or frame['Result'].isna().all():
                raise ValueError(f'{path}: does not contain valid results.')
            index = frame['Result'].idxmin()
            minimum = frame.loc[index, 'Result']
            step = frame.loc[index, 'Step']
            if pd.isna(step):
                raise ValueError(f'{path}: the minimum result has no Step.')
            minimums.append(minimum)
            steps.append(step)
        row = {column: configuration[column] for column in analysis['columns']}
        row.update(zip(METRICS, (sum(minimums) / len(minimums),
                                sum(steps) / len(steps), min(minimums))))
        rows.append(row)
    table = pd.DataFrame(rows, columns=analysis['columns'] + METRICS)
    if analysis['output'] is not None:
        destination = base / analysis['output']
        destination.parent.mkdir(parents=True, exist_ok=True)
        table.to_excel(destination, index=False)
        print(f'Analysis saved to {destination}')
    print(table.to_string(index=False))
    return table
