import sys
from unittest.mock import Mock
import pytest
import main

pytestmark = pytest.mark.unit


def test_removed_terminal_option_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '--terminal'])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 2
    assert 'unrecognized arguments: --terminal' in capsys.readouterr().err


def test_help_does_not_import_desktop(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'tsp_pso.presentation.experiment_gui', None)
    monkeypatch.setattr(sys, 'argv', ['main.py', '--help'])
    with pytest.raises(SystemExit) as error:
        main.main()
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert 'Desktop Experiment Runner' in output
    assert '--terminal' not in output


def test_default_launches_desktop(monkeypatch):
    from tsp_pso.presentation import experiment_gui
    start=Mock()
    monkeypatch.setattr(experiment_gui,'main',start)
    monkeypatch.setattr(sys,'argv',['main.py'])
    main.main()
    start.assert_called_once_with()
