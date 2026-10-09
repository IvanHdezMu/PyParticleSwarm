import sys
from unittest.mock import Mock
import pytest
import main

pytestmark = pytest.mark.unit


def test_terminal_remains_accessible(monkeypatch):
    from tsp_pso import runner
    start=Mock()
    monkeypatch.setattr(runner,'main',start)
    monkeypatch.setattr(sys,'argv',['main.py','--terminal'])
    main.main()
    start.assert_called_once_with()


def test_default_launches_desktop(monkeypatch):
    from tsp_pso import experiment_gui
    start=Mock()
    monkeypatch.setattr(experiment_gui,'main',start)
    monkeypatch.setattr(sys,'argv',['main.py'])
    main.main()
    start.assert_called_once_with()
