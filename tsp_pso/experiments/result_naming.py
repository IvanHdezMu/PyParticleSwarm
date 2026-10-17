"""Shared result filename conventions for execution and analysis."""


def extra_filename_fields(experiment):
    """Include only varying axes omitted by a legacy filename style."""
    fields = []
    if experiment.style in ('fuel', 'bays'):
        fields.extend(((3, 'minR', experiment.minimums), (4, 'maxR', experiment.maximums)))
    if experiment.style != 'fuel':
        fields.extend(((5, 'ring', experiment.rings), (6, 'full', experiment.full_tanks)))
    return [(index, name, values) for index, name, values in fields if len(values) > 1]


def result_filename(experiment, configuration):
    n, c1, opt, minimum, maximum, ring, full, number = configuration
    prefix = f'{experiment.dataset}_True_{n}_{c1}_{opt}'
    if experiment.style == 'fuel':
        suffix = f'{ring}_{full}_{number}'
    elif experiment.style == 'bays':
        suffix = str(number)
    elif experiment.style == 'berlin_grid':
        suffix = f'{experiment.k}_{number}_{minimum}_{maximum}'
    else:
        suffix = f'{experiment.k}_{minimum}_{maximum}_{number}'
    for index, name, _ in extra_filename_fields(experiment):
        suffix += f'_{name}{configuration[index]}'
    return f'{prefix}_{suffix}.xlsx'
