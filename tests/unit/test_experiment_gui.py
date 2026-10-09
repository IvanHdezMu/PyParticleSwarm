"""Widget wiring smoke check when a desktop display is available."""
import tkinter as tk
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def test_gui_free_values_presets_and_live_count():
    from tsp_pso.experiment_gui import ExperimentRunnerApp
    try:
        app = ExperimentRunnerApp()
    except tk.TclError as error:
        pytest.skip(f'Desktop display unavailable: {error}')
    errors=[]
    app.report_callback_exception=lambda *args: errors.append(args)
    try:
        app.update()
        assert app.count_label.cget('text') == 'Planned runs: 1'
        field=app.numeric['particles']
        field.text.set('64'); field.add()
        assert app.configuration.particles == (8,64)
        assert app.count_label.cget('text') == 'Planned runs: 2'
        field.text.set('64'); field.add()
        assert app.configuration.particles == (8,64)
        assert app.run_button.cget('state') == 'disabled'
        field.text.set(''); field.remove(8)
        assert app.configuration.particles == (64,)
        field.remove(64)
        assert app.configuration.particles == (64,)
        app.select_preset(app.presets[10].name)
        assert app.count_label.cget('text') == 'Planned runs: 270'
        app.select_preset(app.presets[17].name)
        assert app.count_label.cget('text') == 'Planned runs: 120'
        assert app.numeric['fuel_capacity'].active
        app.toggle('operators',15)
        app.numeric['k'].text.set('1000000'); app.numeric['k'].add()
        assert app.configuration.k == (10,1000000)
        assert app.count_label.cget('text') == 'Planned runs: 360'
        app.numeric['k'].text.set('unfinished')
        app.toggle('operators',15)
        assert not app.numeric['k'].active
        assert app.run_button.cget('state') == 'normal'
        app.toggle('operators',15)
        assert app.run_button.cget('state') == 'disabled'
        app.numeric['k'].text.set('')
        app.count_var.set('0')
        assert app.run_button.cget('state') == 'disabled'
        app.count_var.set('2')
        assert app.count_label.cget('text') == 'Planned runs: 24'
        app.output_var.set('')
        assert app.run_button.cget('state') == 'disabled'
        app.update()
        assert not errors
    finally:
        app.destroy()
