"""Reserve execution directories and persist their effective configurations."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re


def create_run_directory(experiment, output_dir):
    """Reserve a run directory under output_dir/experiment.dataset and return its Path.

    output_dir is an explicit base path; relative paths remain relative to the
    working directory. Reserve a UTC timestamped directory atomically, retrying
    collisions with __2, __3, etc., then exclusively write run_config.json from
    the experiment dataclass. Save the snapshot even when Excel is disabled.
    Creation and writing errors propagate; a writing failure leaves the reserved
    directory in place.
    """
    created_at = datetime.now(timezone.utc).replace(microsecond=0)

    def compact(values):
        """Summarize an axis in at most 24 filename-safe characters, preserving order."""
        values = tuple(values)
        text = '-'.join(map(str, values)) if len(values) <= 2 else f'{values[0]}-{values[-1]}x{len(values)}'
        return re.sub(r'[^A-Za-z0-9.-]', '-', text)[:24]

    summary = '_'.join(f'{name}{compact(values)}' for name, values in (
        ('N', experiment.particles), ('c1', experiment.steps), ('opt', experiment.opts),
        ('ring', experiment.rings), ('full', experiment.full_tanks),
        ('k', (experiment.k,)), ('min', experiment.minimums), ('max', experiment.maximums),
    ))
    parent = Path(output_dir) / experiment.dataset
    parent.mkdir(parents=True, exist_ok=True)
    stem = f'{created_at:%Y-%m-%d_%H-%M-%S}_{summary}'
    attempt = 1
    while True:
        destination = parent / (stem if attempt == 1 else f'{stem}__{attempt}')
        try:
            destination.mkdir()
            break
        except FileExistsError:
            attempt += 1
    configuration = asdict(experiment)
    configuration['repetitions'] = {'start': experiment.repetitions.start,
                                    'stop': experiment.repetitions.stop,
                                    'step': experiment.repetitions.step}
    configuration['created_at'] = created_at.isoformat()
    with (destination / 'run_config.json').open('x', encoding='utf-8') as stream:
        json.dump(configuration, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return destination

