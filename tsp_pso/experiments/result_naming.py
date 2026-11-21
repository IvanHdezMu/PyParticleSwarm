"""Single scalar formatter shared by modern execution and historical readers."""


def result_filename(dataset, style, k, configuration, extra_fields=()):
    """Format the established eight-value tuple; historical sweeps supply suffix axes."""
    n, c1, opt, minimum, maximum, ring, full, number = configuration
    prefix = f'{dataset}_True_{n}_{c1}_{opt}'
    if style == 'fuel':
        suffix = f'{ring}_{full}_{number}'
    elif style == 'bays':
        suffix = str(number)
    elif style == 'berlin_grid':
        suffix = f'{k}_{number}_{minimum}_{maximum}'
    else:
        suffix = f'{k}_{minimum}_{maximum}_{number}'
    for index, name, _ in extra_fields:
        suffix += f'_{name}{configuration[index]}'
    return f'{prefix}_{suffix}.xlsx'
