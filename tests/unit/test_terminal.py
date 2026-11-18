"""Interactive terminal contracts without launching solvers or a GUI."""
from tsp_pso.infrastructure.experiment_options import load_run_options
from tsp_pso.experiments.experiment import build_experiments
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from tsp_pso.application import runner
from tsp_pso.presentation import terminal

pytestmark = pytest.mark.unit


def answers(monkeypatch, values):
    values = iter(values)
    def read(prompt):
        print(prompt, end='')
        value = next(values)
        if isinstance(value, BaseException):
            raise value
        return value
    monkeypatch.setattr('builtins.input', read)


def test_option_validation_and_custom_numbers(monkeypatch, capsys):
    answers(monkeypatch, ['bad', '1', '9'])
    assert terminal.choose_option('Title', ['first', 'second'], str, numbers=[3, 9]) == 'second'
    assert capsys.readouterr().out == (
        '\nTitle\n 3. first\n 9. second\n 0. Exit\n'
        '\nNumber: Enter a number from the menu.\n'
        '\nNumber: That number is not on the menu.\n\nNumber: ')


@pytest.mark.parametrize('selection', ['0', '1', '2'])
def test_run_menu_order_and_selection(monkeypatch, capsys, selection):
    experiments = build_experiments(load_run_options())[:2]
    execute = Mock()
    monkeypatch.setattr(runner, 'execute', execute)
    answers(monkeypatch, ['1', selection])
    terminal.main(experiments=experiments)
    output = capsys.readouterr().out
    labels = [f'{i:2}. {e.dataset}: {e.label} ({e.count} runs)' for i, e in enumerate(experiments, 1)]
    assert output.index(labels[0]) < output.index(labels[1])
    if selection == '0':
        execute.assert_not_called()
    else:
        execute.assert_called_once_with(experiments[int(selection) - 1], run_options=load_run_options())


@pytest.mark.parametrize('reply', ['y', ' YES ', 'n', '', '0'])
def test_missing_results_confirmation_and_order(monkeypatch, capsys, reply):
    experiment = build_experiments(load_run_options())[0]
    analysis = {'label': 'analysis', 'experiment': {'dataset': experiment.dataset, 'label': experiment.label}}
    monkeypatch.setattr(terminal, 'load_analysis_options', lambda: [{'id': 'historical'}, analysis])
    monkeypatch.setattr(terminal, 'first_missing_result', lambda item: Path('missing.xlsx'))
    events = []
    monkeypatch.setattr(runner, 'execute', lambda item, **kwargs: events.append(('execute', item)))
    monkeypatch.setattr(terminal, 'analyze', lambda item: events.append(('analyze', item)))
    answers(monkeypatch, ['2', '1', reply])
    terminal.main(experiments=[experiment])
    assert events == ([('execute', experiment), ('analyze', analysis)] if reply.strip().lower() in ('y', 'yes') else [])
    assert 'Missing results for option 1: missing.xlsx\nRun option 1 now? [y/N]: ' in capsys.readouterr().out


def test_existing_results_analyzed_without_confirmation(monkeypatch):
    analysis = terminal.load_analysis_options()
    selected = terminal.analysis_menu_options(analysis)[1]
    monkeypatch.setattr(terminal, 'first_missing_result', lambda item: None)
    analyze = Mock()
    execute = Mock()
    monkeypatch.setattr(terminal, 'analyze', analyze)
    monkeypatch.setattr(runner, 'execute', execute)
    answers(monkeypatch, ['2', '1'])
    terminal.main()
    analyze.assert_called_once_with(selected)
    execute.assert_not_called()


@pytest.mark.parametrize('error', [EOFError(), KeyboardInterrupt(), OSError('disk'), ValueError('invalid'), KeyError('missing')])
def test_error_and_cancellation_messages(monkeypatch, capsys, error):
    answers(monkeypatch, ['1', '1'])
    monkeypatch.setattr(runner, 'execute', Mock(side_effect=error))
    terminal.main()
    output = capsys.readouterr().out
    expected = ('\nOperation cancelled.\n' if isinstance(error, (EOFError, KeyboardInterrupt))
                else f'Could not complete the operation: {error}\n')
    assert output.endswith(expected)


def test_runner_main_compatibility(monkeypatch):
    start = Mock()
    monkeypatch.setattr(terminal, 'main', start)
    runner.main()
    start.assert_called_once_with()


@pytest.mark.parametrize('input_text', ['0\n', '1\n0\n', '2\n0\n', ''])
def test_actual_terminal_entry_point(input_text):
    result = subprocess.run([sys.executable, 'main.py', '--terminal'], input=input_text,
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('\nWhat do you want to do?\n 1. run — Execute\n 2. analysis — Analyze results\n 0. Exit\n\nNumber: ')
    if input_text == '':
        assert result.stdout.endswith('\nOperation cancelled.\n')


def test_disabled_excel_without_snapshots_does_not_offer_execution(monkeypatch, tmp_path, capsys):
    from tsp_pso.analysis import analysis

    options = load_run_options()
    options['experiments'][0]['excel'] = False
    options['output_dir'] = str(tmp_path)
    monkeypatch.setattr(terminal, 'load_run_options', lambda: options)
    monkeypatch.setattr(analysis, 'load_run_options', lambda path=None: options)
    execute = Mock()
    monkeypatch.setattr(runner, 'execute', execute)
    answers(monkeypatch, ['2', '1'])
    terminal.main()
    output = capsys.readouterr().out
    assert 'excel=false' in output
    assert 'No saved Excel runs are available' in output
    assert 'Run option 1 now?' not in output
    execute.assert_not_called()
