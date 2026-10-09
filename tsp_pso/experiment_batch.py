"""Metadata validation, conditional lazy expansion and editable legacy presets."""
from dataclasses import asdict, dataclass
from itertools import product, islice
import json
from math import prod
from pathlib import Path

from .experiment_config import ExperimentConfiguration, RepetitionSpec, is_parameter_active

ROOT = Path(__file__).resolve().parents[1]
EXPANSION_VERSION = 1
CONDITIONAL = (
    'k', 'primary_operator_share', 'minimum_reset_probability',
    'maximum_reset_probability', 'reset_threshold_divisor', 'fuel_capacity',
    'consumption', 'full_initial_tank', 'progress_warmup_multiplier',
)
DEFAULTS = dict(k=10, primary_operator_share=0.2, minimum_reset_probability=0.2,
                maximum_reset_probability=0.8, reset_threshold_divisor=1000,
                fuel_capacity=150.0, consumption=7.0, full_initial_tank=False,
                progress_warmup_multiplier=5)


@dataclass(frozen=True)
class DatasetDescriptor:
    id: str
    filename: str
    format: str
    source: str
    problem_types: tuple[str, ...]


def load_catalog():
    with (ROOT / 'config/datasets.json').open(encoding='utf-8') as stream:
        return tuple(DatasetDescriptor(id=name, **{**data, 'problem_types': tuple(data['problem_types'])})
                     for name, data in json.load(stream)['datasets'].items())


@dataclass(frozen=True)
class ConcreteRunConfiguration:
    dataset: str
    problem_mode: str
    operator: int
    permutation_reset: bool
    particles: int
    c1: int
    ring: bool
    k: int | None
    primary_operator_share: float | None
    minimum_reset_probability: float | None
    maximum_reset_probability: float | None
    reset_threshold_divisor: float | None
    fuel_capacity: float | None
    consumption: float | None
    full_initial_tank: bool | None
    progress_warmup_multiplier: float | None
    repetition_id: int
    verbose: bool
    excel: bool
    output_dir: Path
    name: str
    legacy_style: str
    legacy_label: str | None
    analysis_output: str | None
    legacy_values: tuple[tuple[str, object], ...]

    def to_dict(self):
        data = asdict(self)
        data['output_dir'] = str(self.output_dir)
        data['legacy_values'] = dict(self.legacy_values)
        return data


@dataclass(frozen=True)
class ExpansionPlan:
    configuration: ExperimentConfiguration
    datasets: tuple[DatasetDescriptor, ...]


def compile_plan(configuration, catalog=None):
    if not isinstance(configuration, ExperimentConfiguration):
        raise ValueError('Expected ExperimentConfiguration')
    catalog = load_catalog() if catalog is None else tuple(catalog)
    by_id = {item.id: item for item in catalog}
    selected = []
    for name in configuration.datasets:
        if name not in by_id:
            raise ValueError(f'Unknown dataset: {name}')
        item = by_id[name]
        for mode in configuration.problem_modes:
            if mode not in item.problem_types:
                raise ValueError(f'{name} does not support {mode.upper()}')
        selected.append(item)
    return ExpansionPlan(configuration, tuple(selected))


def _branches(plan):
    c = plan.configuration
    for dataset, mode, operator, reset in product(
            c.datasets, c.problem_modes, c.operators, c.permutation_reset):
        axes = [c.particles, c.c1, c.ring]
        for field in CONDITIONAL:
            active = is_parameter_active(field, problem_mode=mode, operator=operator,
                                         permutation_reset=reset, verbose=c.verbose, excel=c.excel)
            axes.append(getattr(c, field) if active else (None,))
        yield (dataset, mode, operator, reset), axes


def count_runs(plan):
    return sum(prod(len(axis) for axis in axes) for _, axes in _branches(plan)) * plan.configuration.repetitions.count


def iterate_runs(plan):
    c = plan.configuration
    fallbacks = {name: getattr(c, name)[0] if len(getattr(c, name)) == 1 else DEFAULTS[name]
                 for name in CONDITIONAL}
    for (dataset, mode, operator, reset), axes in _branches(plan):
        for values in product(*axes):
            n, c1, ring, *conditional = values
            science = dict(zip(CONDITIONAL, conditional))
            effective = tuple((name, fallbacks[name] if value is None else value)
                              for name, value in science.items())
            for offset in range(c.repetitions.count):
                yield ConcreteRunConfiguration(
                    dataset=dataset, problem_mode=mode, operator=operator,
                    permutation_reset=reset, particles=n, c1=c1, ring=ring, **science,
                    repetition_id=c.repetitions.first_id + offset, verbose=c.verbose,
                    excel=c.excel, output_dir=c.output_dir, name=c.name,
                    legacy_style=c.legacy_style, legacy_label=c.legacy_label, analysis_output=c.analysis_output,
                    legacy_values=effective)


def preview_runs(plan, limit=5):
    if type(limit) is not int or limit < 0:
        raise ValueError('Preview limit must be a nonnegative integer')
    return tuple(islice(iterate_runs(plan), limit))


def load_presets():
    # Read JSON, not runner globals: importing presets never loads a matrix/solver.
    with (ROOT / 'config/experiments.json').open(encoding='utf-8') as stream:
        options = json.load(stream)
    presets = []
    for entry in options['experiments']:
        e = {**options['defaults'], **entry}
        presets.append(ExperimentConfiguration(
            name=f"{e['dataset']}: {e['label']}", datasets=(e['dataset'],),
            problem_modes=('tspwr' if e['refuel'] else 'tsp',),
            particles=e['particles'], c1=e['steps'], operators=e['opts'], k=(e['k'],),
            ring=e['rings'], permutation_reset=(e['permut_reset'],),
            minimum_reset_probability=e['minimums'], maximum_reset_probability=e['maximums'],
            fuel_capacity=(e['max_capacity'],), consumption=(e['consumption'],),
            full_initial_tank=e['full_tanks'], reset_threshold_divisor=(e['reset_threshold_divisor'],),
            primary_operator_share=(e['primary_operator_share'],),
            progress_warmup_multiplier=(e['progress_warmup_multiplier'],),
            repetitions=RepetitionSpec(e['repetitions']['stop'] - e['repetitions']['start'],
                                       e['repetitions']['start']),
            verbose=e['verbose'], excel=e['excel'], output_dir=options['output_dir'],
            legacy_style=e['style'], legacy_label=e['label'], analysis_output=e.get('analysis_output')))
    return tuple(presets)
