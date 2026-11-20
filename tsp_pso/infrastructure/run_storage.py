"""Reserve execution directories and persist their effective configurations."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re


def create_run_directory(run, output_dir, values):
    """Reserve one concrete run's directory and persist the historical JSON schema.

    values is the effective scalar mapping already read by the caller. Relative
    output paths use the working directory. Reserve atomically, never overwrite,
    and keep partial artifacts if snapshot writing or subsequent execution fails.
    """
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    summary = '_'.join(name + re.sub(r'[^A-Za-z0-9.-]', '-', str(value))[:24]
                       for name, value in (
                           ('N', run.particles), ('c1', run.c1), ('opt', run.operator),
                           ('ring', run.ring), ('full', values['full_initial_tank']),
                           ('k', values['k']), ('min', values['minimum_reset_probability']),
                           ('max', values['maximum_reset_probability'])))
    parent = Path(output_dir) / run.dataset
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
    configuration = dict(
        dataset=run.dataset, label=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', run.legacy_label or run.name),
        steps=(run.c1,), particles=(run.particles,), opts=(run.operator,),
        minimums=(values['minimum_reset_probability'],), maximums=(values['maximum_reset_probability'],),
        rings=(run.ring,), full_tanks=(values['full_initial_tank'],),
        repetitions=dict(start=run.repetition_id, stop=run.repetition_id + 1, step=1),
        excel=run.excel, refuel=run.problem_mode == 'tspwr', style=run.legacy_style,
        max_capacity=values['fuel_capacity'], consumption=values['consumption'],
        permut_reset=run.permutation_reset, k=values['k'], analysis_output=run.analysis_output,
        reset_threshold_divisor=values['reset_threshold_divisor'],
        primary_operator_share=values['primary_operator_share'],
        progress_warmup_multiplier=values['progress_warmup_multiplier'], verbose=run.verbose)
    configuration['created_at'] = created_at.isoformat()
    with (destination / 'run_config.json').open('x', encoding='utf-8') as stream:
        json.dump(configuration, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return destination
