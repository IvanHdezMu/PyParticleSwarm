"""Small GUI-independent editing operations; validation remains in the model."""
from dataclasses import replace

from ..experiments.experiment_config import ExperimentConfiguration
from ..experiments.experiment_batch import compile_plan, count_runs

# NUMERIC_FIELDS: Numeric input labels and accepted types for the GUI.
# ExperimentConfiguration performs the final value validation.
NUMERIC_FIELDS = {
    'particles': ('Number of particles', int), 'c1': ('Search effort (c1)', int),
    'k': ('Segment length (k)', int),
    'minimum_reset_probability': ('Minimum reset probability', float),
    'maximum_reset_probability': ('Maximum reset probability', float),
    'reset_threshold_divisor': ('Reset threshold divisor', float),
    'primary_operator_share': ('Primary operator share', float),
    'fuel_capacity': ('Fuel capacity (L)', float),
    'consumption': ('Fuel efficiency (km/L)', float),
    'progress_warmup_multiplier': ('Progress warmup multiplier', float),
}
# OPERATOR_LABELS: Operator IDs and labels displayed in the GUI.
# Their insertion order determines the order of the selectable operators.
OPERATOR_LABELS = {
    1: 'Segment flip (2-opt)', 2: 'Node relocation (2.5-opt)', 3: 'Node swap (2-opt)',
    4: 'k-segment flip', 5: 'k-segment random (legacy)',
    10: 'Adaptive flip / relocation', 12: 'Mixed flip + relocation',
    15: 'Mixed flip + k-random', 21: 'Mixed relocation + flip',
}


def parse_numeric(field, text):
    if field not in NUMERIC_FIELDS:
        raise ValueError(f'Unknown numeric field: {field}')
    try:
        # Preserve integer inputs, including integers too large for float conversion.
        try:
            value = int(text)
        except ValueError:
            if NUMERIC_FIELDS[field][1] is int:
                raise
            value = float(text)
    except (ValueError, TypeError):
        raise ValueError(f'{NUMERIC_FIELDS[field][0]} requires a valid number') from None
    return value


def add_numeric(configuration, field, text):
    value = parse_numeric(field, text)
    return replace(configuration, **{field: (*getattr(configuration, field), value)})


def remove_value(configuration, field, value):
    values = tuple(item for item in getattr(configuration, field) if item != value)
    return replace(configuration, **{field: values})


def toggle_value(configuration, field, value):
    values = getattr(configuration, field)
    if value in values:
        return remove_value(configuration, field, value)
    return replace(configuration, **{field: (*values, value)})


def review(configuration, catalog):
    plan = compile_plan(configuration, catalog)
    warnings = []
    if not configuration.excel:
        warnings.append('Excel is off: the legacy runner saves configuration, but no numerical result file.')
    if any(low > high for low in configuration.minimum_reset_probability
           for high in configuration.maximum_reset_probability) and True in configuration.permutation_reset:
        warnings.append('Some minimum reset probabilities exceed maximums; values will be preserved.')
    if 'tspwr' in configuration.problem_modes:
        warnings.append('The existing refueling heuristic does not enforce route feasibility.')
    return plan, count_runs(plan), tuple(warnings)
