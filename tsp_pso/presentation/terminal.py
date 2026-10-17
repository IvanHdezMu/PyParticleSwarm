"""Interactive terminal menus for running experiments and analyzing results."""
from ..application import runner
from ..analysis.analysis import analyze, first_missing_result, load_analysis_options


def choose_option(title, options, describe, numbers=None):
    """Prompt until a displayed number is selected; zero cancels the selection."""
    numbered_options = dict(zip(numbers if numbers is not None else range(1, len(options) + 1),
                                options))
    print(f'\n{title}')
    for number, option in numbered_options.items():
        print(f'{number:2}. {describe(option)}')
    print(' 0. Exit')
    while True:
        try:
            choice = int(input('\nNumber: '))
        except ValueError:
            print('Enter a number from the menu.')
            continue
        if choice == 0:
            return None
        if choice in numbered_options:
            return numbered_options[choice]
        print('That number is not on the menu.')


def choose_experiment():
    """Select from the current runner catalog in its configured order."""
    return choose_option('What do you want to run?', runner.EXPERIMENTS,
                         lambda experiment: f'{experiment.dataset}: {experiment.label} '
                         f'({experiment.count} runs)')


def analysis_menu_options(analyses):
    """Show the same experiments in the same order as run."""
    by_experiment = {(a['experiment']['dataset'], a['experiment']['label']): a
                     for a in analyses if 'experiment' in a}
    return {number: by_experiment[(experiment.dataset, experiment.label)]
            for number, experiment in enumerate(runner.EXPERIMENTS, 1)}


def main():
    """Run the interactive execution/analysis menu, reporting errors and cancellation."""
    try:
        mode = choose_option('What do you want to do?', ('run', 'analysis'),
                             lambda mode: 'run — Execute' if mode == 'run' else 'analysis — Analyze results')
        if mode == 'run':
            experiment = choose_experiment()
            if experiment is not None:
                runner.execute(experiment)
        elif mode == 'analysis':
            numbered = analysis_menu_options(load_analysis_options())
            counts = {(experiment.dataset, experiment.label): experiment.count
                      for experiment in runner.EXPERIMENTS}
            analysis = choose_option('Which results do you want to analyze?', list(numbered.values()),
                                     lambda option: f"{option['label']} "
                                     f"({counts[(option['experiment']['dataset'], option['experiment']['label'])]} runs)",
                                     numbers=numbered)
            if analysis is not None:
                number = next(number for number, item in numbered.items() if item is analysis)
                missing = first_missing_result(analysis)
                if missing is not None:
                    print(f'Missing results for option {number}: {missing}')
                    if input(f'Run option {number} now? [y/N]: ').strip().lower() not in ('y', 'yes'):
                        return
                    runner.execute(runner.EXPERIMENTS[number - 1])
                analyze(analysis)
    except (EOFError, KeyboardInterrupt):
        print('\nOperation cancelled.')
    except (OSError, ValueError, KeyError) as error:
        print(f'Could not complete the operation: {error}')

