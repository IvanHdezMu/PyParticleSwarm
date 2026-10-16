"""Widget wiring smoke check when a desktop display is available."""
import tkinter as tk

import pytest

pytestmark = pytest.mark.unit


def test_gui_free_values_presets_and_live_count():
    from tsp_pso.presentation.experiment_gui import ExperimentRunnerApp
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
        assert app.refuel_card.winfo_manager() == 'grid'
        assert 'fuel_capacity' not in app.numeric
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


def test_simplified_controls_and_preset_edit_safety():
    from tsp_pso.presentation.experiment_gui import ExperimentRunnerApp
    try:
        app = ExperimentRunnerApp()
    except tk.TclError as error:
        pytest.skip(f'Desktop display unavailable: {error}')
    try:
        app.update()
        assert app.numeric['particles'].label.cget('text') == 'Number of particles'
        assert app.numeric['c1'].label.cget('text') == 'Search effort (c1)'
        assert app.numeric['k'].label.cget('text') == 'Segment length (k)'
        assert 'scales with the number of nodes' in app.numeric['c1'].help_label.cget('text')
        assert not app.advanced_open
        assert app.advanced_content.winfo_manager() == ''
        for field in ('first_id', 'output_dir'):
            assert app.scalar_rows[field].master is app.advanced_content
        for field in ('reset_threshold_divisor', 'progress_warmup_multiplier'):
            assert app.numeric[field].master.master is app.advanced_content
        app.toggle_advanced()
        assert app.advanced_content.winfo_manager() == 'pack'
        app.toggle_advanced()
        assert app.advanced_content.winfo_manager() == ''

        app.dataset_selector._select('Minas24D')
        assert app.configuration.datasets == ('Minas24D',)
        assert app.problem_selector._values == ['TSP', 'TSPWR']
        app.problem_selector._select('TSPWR')
        assert app.configuration.problem_modes == ('tspwr',)
        assert app.refuel_card.winfo_manager() == 'grid'
        app.fuel_capacity_var.set('234.5')
        app.consumption_var.set('8.125')
        assert app.current_configuration().fuel_capacity == (234.5,)
        assert app.current_configuration().consumption == (8.125,)
        assert 'consumption' not in app.numeric
        app.fuel_capacity_var.set('0')
        assert app.run_button.cget('state') == 'disabled'
        app.fuel_capacity_var.set('234.5')
        app.dataset_selector._select('berlin52')
        assert app.configuration.datasets == ('berlin52',)
        assert app.configuration.problem_modes == ('tsp',)
        assert app.problem_selector._values == ['TSP']
        assert app.refuel_card.winfo_manager() == ''
        app.source_filter._select('Ottoni et al. (2022)')
        assert len(app.configuration.datasets) == 1
        assert app.configuration.datasets[0] in app.dataset_selector._values

        assert app.numeric['k'].winfo_manager() == ''
        assert app.numeric['primary_operator_share'].winfo_manager() == ''
        app.toggle('operators', 15)
        assert app.numeric['k'].winfo_manager() == 'grid'
        assert app.numeric['primary_operator_share'].winfo_manager() == 'grid'
        assert '0.2 = 20%' in app.numeric['primary_operator_share'].help_label.cget('text')
        app.toggle('operators', 15)
        assert app.numeric['k'].winfo_manager() == ''
        app.toggle('permutation_reset', False)
        app.toggle('permutation_reset', True)
        assert app.numeric['minimum_reset_probability'].winfo_manager() == ''
        assert app.numeric['maximum_reset_probability'].winfo_manager() == ''
        app.toggle('permutation_reset', True)
        assert app.numeric['minimum_reset_probability'].winfo_manager() == 'grid'

        for preset in app.presets:
            app.select_preset(preset.name)
            assert app.current_configuration() == preset
            assert len(app.configuration.datasets) == len(app.configuration.problem_modes) == 1
        preset = app.presets[15]
        app.select_preset(preset.name)
        assert app.first_var.get() == '17'
        assert not app.advanced_open
        app.numeric['particles'].text.set('123456')
        app.numeric['particles'].add()
        app.fuel_capacity_var.set('333')
        assert app.presets[15] is preset
        assert preset.particles == (16,) and preset.fuel_capacity == (150.0,)
        app.select_preset('Custom configuration')
        assert app.first_var.get() == '1'
        tank = [(value, button.cget('text')) for field,value,_,button in app.choice_controls
                if field == 'full_initial_tank']
        assert tank == [(False, 'Empty'), (True, 'Full')]
    finally:
        app.destroy()
