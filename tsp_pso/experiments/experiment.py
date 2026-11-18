"""Traditional experiment model and construction from explicit options."""

from dataclasses import dataclass
from itertools import product
from math import prod


@dataclass(frozen=True)
class Experiment:
    """Traditional experiment sweep, preserving the complete Cartesian product.

    Repetition IDs are labels, not random seeds. Unlike batch expansion, this
    model keeps every configured axis, including conditionally inactive values.
    """

    dataset: str
    label: str
    steps: tuple
    particles: tuple = (8,)
    opts: tuple = (10,)
    minimums: tuple = (0.2,)
    maximums: tuple = (0.8,)
    rings: tuple = (True,)
    full_tanks: tuple = (False,)
    repetitions: range = range(1, 2)
    excel: bool = False
    refuel: bool = False
    style: str = 'standard'
    max_capacity: float = 150.0
    consumption: float = 7.0
    permut_reset: bool = True
    k: int = 10
    analysis_output: str | None = None
    reset_threshold_divisor: float = 1000
    primary_operator_share: float = 0.2
    progress_warmup_multiplier: float = 5
    verbose: bool = True

    def configurations(self):
        """Return the Cartesian-product iterator in filename/solver parameter order.

        Tuples contain particles, steps, operator, minimum, maximum, ring mode,
        initial-tank mode and repetition ID; repetition varies fastest.
        """
        return product(self.particles, self.steps, self.opts, self.minimums,
                       self.maximums, self.rings, self.full_tanks, self.repetitions)

    @property
    def count(self):
        """Return the size of the full configuration product."""
        return prod(len(values) for values in (self.particles, self.steps, self.opts,
                    self.minimums, self.maximums, self.rings, self.full_tanks, self.repetitions))


def build_experiments(options):
    """Build ordered experiments from explicitly supplied configuration options.

    Entry values replace defaults shallowly. Preserve list validation, conversion
    to tuples and the original start/stop repetition ranges without loading files.
    Return a list in input order without mutating options. Unknown datasets, empty
    axes and empty repetition ranges raise ValueError; missing keys raise KeyError.
    """
    experiments = []
    for entry in options['experiments']:
        values = {**options['defaults'], **entry}
        if values['dataset'] not in options['datasets']:
            raise ValueError(f"Unknown dataset: {values['dataset']}")
        for field in ('steps', 'particles', 'opts', 'minimums', 'maximums',
                      'rings', 'full_tanks'):
            if not isinstance(values[field], list) or not values[field]:
                raise ValueError(f"{field} must be a non-empty list.")
            values[field] = tuple(values[field])
        repetitions = values['repetitions']
        values['repetitions'] = range(repetitions['start'], repetitions['stop'])
        if not values['repetitions']:
            raise ValueError('The repetition range cannot be empty.')
        experiments.append(Experiment(**values))
    return experiments
