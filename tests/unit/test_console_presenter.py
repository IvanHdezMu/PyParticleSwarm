"""Exact console layout, independent of the solver and its mutable state."""

import pytest

from tsp_pso.presentation.console_presenter import ConsolePresenter

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('label, result', [('DISTANCE', 9), ('REFUEL COST', 18)])
def test_console_format_and_prints(capsys, label, result):
    presenter = ConsolePresenter()
    text = presenter.format_result(7, label, result, '[0 1 2 3]')
    expected = (f'PARTICLE SWARM: \nCURRENT STEPS: 7 \nBEST {label}: {result:.6f} \n'
                'BEST MEMBER: [0 1 2 3] \n\n')
    assert text == expected
    assert capsys.readouterr().out == ''
    presenter.present_result(text)
    presenter.present_completion()
    presenter.present_result(text)
    assert capsys.readouterr().out == (
        expected + '\nTERMINATING - REACHED MAXIMUM STEPS\n' + expected + '\n')
