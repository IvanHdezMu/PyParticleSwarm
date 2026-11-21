"""Single scalar formatter shared by execution and batch analysis."""


def result_filename(dataset, style, k, configuration):
    """Format the established eight-value tuple."""
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
    return f'{prefix}_{suffix}.xlsx'
