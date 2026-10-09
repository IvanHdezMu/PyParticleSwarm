"""Immutable user-requested experiment settings, independent of execution.

This module does not load datasets or invoke the runner. Numeric values retain
ordinary Python semantics; in particular, requested k values are never clamped.
"""

from dataclasses import asdict, dataclass, fields
from math import isfinite
from pathlib import Path


SUPPORTED_PROBLEM_MODES = frozenset({'tsp', 'tspwr'})
SUPPORTED_OPERATORS = frozenset({1, 2, 3, 4, 5, 10, 12, 15, 21})
OPERATORS_USING_K = frozenset({4, 5, 15})
OPERATORS_USING_PRIMARY_SHARE = frozenset({12, 15, 21})
FUEL_FIELDS = frozenset({'fuel_capacity', 'consumption', 'full_initial_tank'})
RESET_FIELDS = frozenset({
    'minimum_reset_probability', 'maximum_reset_probability',
    'reset_threshold_divisor',
})


def is_parameter_active(name, *, problem_mode, operator, permutation_reset,
                        verbose=False, excel=True):
    """Return applicability for a validated scalar selection, without expansion.

    Inactive values remain part of user intent. The future runner adapter must
    still forward safe legacy arguments (notably a positive reset divisor).
    """
    if name == 'k':
        return operator in OPERATORS_USING_K
    if name == 'primary_operator_share':
        return operator in OPERATORS_USING_PRIMARY_SHARE
    if name in FUEL_FIELDS:
        return problem_mode == 'tspwr'
    if name in RESET_FIELDS:
        return permutation_reset
    if name == 'progress_warmup_multiplier':
        return verbose or excel
    if name in _SWEEP_FIELDS:
        return True
    raise ValueError(f'Unknown scientific parameter: {name}')


def _positive_integer(name, value, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')


def _number(name, value, *, minimum=0, maximum=None, exclusive=False):
    # Do not convert integers to float: arbitrarily large integers are valid.
    if type(value) not in (int, float) or (type(value) is float and not isfinite(value)):
        raise ValueError(f'{name} must be a finite int or float')
    if value < minimum or (exclusive and value == minimum):
        comparison = '>' if exclusive else '>='
        raise ValueError(f'{name} must be {comparison} {minimum}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name} must be <= {maximum}')


@dataclass(frozen=True)
class RepetitionSpec:
    """Consecutive repetition labels; these IDs are not random seeds."""

    count: int = 1
    first_id: int = 1

    def __post_init__(self):
        _positive_integer('repetitions.count', self.count)
        _positive_integer('repetitions.first_id', self.first_id)


_INTEGER_FIELDS = {'particles': 2, 'c1': 1, 'k': 1}
_BOOLEAN_FIELDS = ('ring', 'permutation_reset', 'full_initial_tank')
_PROBABILITY_FIELDS = (
    'minimum_reset_probability', 'maximum_reset_probability',
    'primary_operator_share',
)
_POSITIVE_FIELDS = ('fuel_capacity', 'consumption', 'reset_threshold_divisor')
_SWEEP_FIELDS = (
    'datasets', 'problem_modes', 'particles', 'c1', 'operators', 'k',
    *_BOOLEAN_FIELDS, *_PROBABILITY_FIELDS, *_POSITIVE_FIELDS,
    'progress_warmup_multiplier',
)


@dataclass(frozen=True)
class ExperimentConfiguration:
    """Requested batch settings; conditional fields retain their original values.

    Lists are accepted at construction and copied to tuples for edit safety.
    Dataset IDs need not be registered yet. c1 is a node-scaled search budget;
    consumption is measured in km/liter. There is no dataset-dependent validation.
    """

    datasets: tuple[str, ...]
    name: str = 'Untitled batch'
    problem_modes: tuple[str, ...] = ('tsp',)
    particles: tuple[int, ...] = (8,)
    c1: tuple[int, ...] = (1200,)
    operators: tuple[int, ...] = (10,)
    k: tuple[int, ...] = (10,)
    ring: tuple[bool, ...] = (True,)
    permutation_reset: tuple[bool, ...] = (True,)
    minimum_reset_probability: tuple[float, ...] = (0.2,)
    maximum_reset_probability: tuple[float, ...] = (0.8,)
    fuel_capacity: tuple[float, ...] = (150.0,)
    consumption: tuple[float, ...] = (7.0,)
    full_initial_tank: tuple[bool, ...] = (False,)
    reset_threshold_divisor: tuple[float, ...] = (1000,)
    primary_operator_share: tuple[float, ...] = (0.2,)
    progress_warmup_multiplier: tuple[float, ...] = (5,)
    repetitions: RepetitionSpec = RepetitionSpec()
    verbose: bool = False
    excel: bool = True
    output_dir: Path = Path('Results')

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('name must be a nonempty string')
        for name in _SWEEP_FIELDS:
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or not values:
                raise ValueError(f'{name} must be a nonempty list or tuple')
            object.__setattr__(self, name, tuple(values))

        for value in self.datasets:
            if not isinstance(value, str) or not value.strip():
                raise ValueError('datasets must contain nonempty string IDs')
        for value in self.problem_modes:
            if type(value) is not str or value not in SUPPORTED_PROBLEM_MODES:
                raise ValueError(f'Unsupported problem mode: {value!r}')
        for value in self.operators:
            if type(value) is not int or value not in SUPPORTED_OPERATORS:
                raise ValueError(f'Unsupported operator: {value!r}')
        for name, minimum in _INTEGER_FIELDS.items():
            for value in getattr(self, name):
                _positive_integer(name, value, minimum)
        for name in _BOOLEAN_FIELDS:
            if any(type(value) is not bool for value in getattr(self, name)):
                raise ValueError(f'{name} must contain bool values')
        for name in _PROBABILITY_FIELDS:
            for value in getattr(self, name):
                _number(name, value, maximum=1)
        for name in _POSITIVE_FIELDS:
            for value in getattr(self, name):
                _number(name, value, exclusive=True)
        for value in self.progress_warmup_multiplier:
            _number('progress_warmup_multiplier', value)

        # Values are now validated scalar types; normal Python equality applies.
        for name in _SWEEP_FIELDS:
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f'{name} contains duplicate values')
        if not isinstance(self.repetitions, RepetitionSpec):
            raise ValueError('repetitions must be a RepetitionSpec')
        for name in ('verbose', 'excel'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be a bool')
        if not isinstance(self.output_dir, (str, Path)) or not str(self.output_dir).strip():
            raise ValueError('output_dir must be a nonempty path')
        object.__setattr__(self, 'output_dir', Path(self.output_dir))

    def to_dict(self):
        """Return detached JSON-compatible data with ordinary numeric values."""
        result = asdict(self)
        for name in _SWEEP_FIELDS:
            result[name] = list(result[name])
        result['output_dir'] = str(self.output_dir)
        return result

    @classmethod
    def from_dict(cls, data):
        """Load JSON-style data through the same validation as construction."""
        if not isinstance(data, dict):
            raise ValueError('configuration must be a dictionary')
        values = dict(data)
        unknown = values.keys() - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f'Unknown configuration fields: {sorted(unknown)}')
        if 'datasets' not in values:
            raise ValueError('datasets is required')
        if 'repetitions' in values:
            spec = values['repetitions']
            if not isinstance(spec, dict) or spec.keys() - {'count', 'first_id'}:
                raise ValueError('repetitions must contain only count and first_id')
            values['repetitions'] = RepetitionSpec(**spec)
        return cls(**values)
