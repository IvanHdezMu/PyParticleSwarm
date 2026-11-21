"""Focused checks for solver parameter forwarding from experiment configuration."""
from dataclasses import replace
from unittest.mock import Mock

import numpy as np
import pytest
from conftest import concrete_run

from tsp_pso.algorithms.core.pso_config import PSOConfig
from tsp_pso.algorithms.tspwr.refuel_config import RefuelConfig
from tsp_pso.application import runner
from tsp_pso.experiments.experiment_batch import (
    build_presets,
    compile_plan,
    count_runs,
    iterate_runs,
)
from tsp_pso.experiments.experiment_config import ExperimentConfiguration
from tsp_pso.infrastructure.experiment_options import (
    load_catalog_options,
    load_preset_options,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('override', [None, 1])
def test_reset_threshold_divisor_config_and_forwarding(monkeypatch, tmp_path, override):
    options = load_preset_options()
    assert options['defaults']['reset_threshold_divisor'] == 1000
    options['experiments'] = [options['experiments'][0]]
    options['experiments'][0]['excel'] = False
    if override is not None:
        options['experiments'][0]['reset_threshold_divisor'] = override
    experiment, = build_presets(options)
    assert experiment.reset_threshold_divisor[0] == (1000 if override is None else override)

    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(concrete_run(experiment), output_dir=tmp_path, dataset={})
    factory.assert_called_once()
    assert factory.call_args.kwargs['config'].reset_threshold_divisor == experiment.reset_threshold_divisor[0]
    factory.return_value.run.assert_called_once()


@pytest.mark.parametrize('override', [None, 0.5])
def test_primary_operator_share_config_and_forwarding(monkeypatch, tmp_path, override):
    options = load_preset_options()
    assert options['defaults']['primary_operator_share'] == 0.2
    options['experiments'] = [options['experiments'][0]]
    options['experiments'][0]['excel'] = False
    if override is not None:
        options['experiments'][0]['primary_operator_share'] = override
    experiment, = build_presets(options)
    assert experiment.primary_operator_share[0] == (0.2 if override is None else override)

    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(concrete_run(experiment), output_dir=tmp_path, dataset={})
    factory.assert_called_once()
    assert factory.call_args.kwargs['config'].primary_operator_share == experiment.primary_operator_share[0]
    factory.return_value.run.assert_called_once()


@pytest.mark.parametrize('override', [None, 1])
def test_progress_warmup_multiplier_config_and_forwarding(monkeypatch, tmp_path, override):
    options = load_preset_options()
    assert options['defaults']['progress_warmup_multiplier'] == 5
    options['experiments'] = [options['experiments'][0]]
    options['experiments'][0]['excel'] = False
    if override is not None:
        options['experiments'][0]['progress_warmup_multiplier'] = override
    experiment, = build_presets(options)
    assert experiment.progress_warmup_multiplier[0] == (5 if override is None else override)

    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(concrete_run(experiment), output_dir=tmp_path, dataset={})
    factory.assert_called_once()
    assert factory.call_args.kwargs['config'].progress_warmup_multiplier == experiment.progress_warmup_multiplier[0]
    factory.return_value.run.assert_called_once()


def test_existing_experiment_verbose_behavior(monkeypatch, tmp_path):
    assert load_preset_options()['defaults']['verbose'] is True
    assert ExperimentConfiguration(
        datasets=('Minas24D',), legacy_label='individual', c1=(1200,), excel=False, verbose=True,
    ).verbose is True
    assert all('verbose' not in dataset for dataset in load_catalog_options()['datasets'].values())
    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (np.array([[0, 2], [2, 0]]), None))
    assert len(build_presets(load_preset_options())) == 22
    for number, experiment in enumerate(build_presets(load_preset_options()), 1):
        # Berlin52 and Bays29 were quiet; the other individual runs were verbose.
        assert experiment.verbose is (3 <= number <= 10)
        factory.reset_mock()
        for run in iterate_runs(compile_plan(experiment)):
            runner.execute(run, output_dir=tmp_path, dataset={})
        assert factory.return_value.run.call_count == count_runs(compile_plan(experiment))
        for call in factory.return_value.run.call_args_list:
            assert call.kwargs['verbose'] is (3 <= number <= 10)


@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('label', ['individual', 'renamed experiment'])
@pytest.mark.parametrize('excel', [False, True])
def test_experiment_verbose_override(monkeypatch, tmp_path, verbose, label, excel):
    options = load_preset_options()
    options['defaults']['verbose'] = not verbose
    options['experiments'] = [{
        'dataset': 'berlin52', 'label': label, 'steps': [2],
        'verbose': verbose, 'excel': excel,
    }]
    experiment, = build_presets(options)
    assert experiment.verbose is verbose
    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(concrete_run(experiment), output_dir=tmp_path, dataset={})
    factory.return_value.run.assert_called_once()
    assert factory.return_value.run.call_args.kwargs['verbose'] is verbose
    assert factory.return_value.run.call_args.kwargs['excel'] is excel


@pytest.mark.parametrize('refuel', [False, True])
def test_solver_class_selection(monkeypatch, tmp_path, refuel):
    tsp_factory = Mock()
    tspwr_factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (tsp_factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (tspwr_factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    matrix = np.array([[0, 2], [2, 0]])
    prices = np.array([1.5, 1.7])
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (matrix, prices))
    experiment = ExperimentConfiguration(
        datasets=('Minas24D',), legacy_label='class selection', c1=(2,),
        problem_modes=('tspwr' if refuel else 'tsp',), excel=False, verbose=True,
    )

    runner.execute(concrete_run(experiment), output_dir=tmp_path, dataset={})

    selected, unused = (tspwr_factory, tsp_factory) if refuel else (tsp_factory, tspwr_factory)
    selected.assert_called_once()
    unused.assert_not_called()
    assert 'refuel_mode' not in selected.call_args.kwargs
    assert isinstance(selected.call_args.kwargs['config'], PSOConfig)
    assert selected.call_args.kwargs['matrix'] is matrix
    if refuel:
        assert isinstance(selected.call_args.kwargs['refuel'], RefuelConfig)
        assert selected.call_args.kwargs['prices'] is prices
        assert selected.call_args.kwargs['refuel'].max_capacity == experiment.fuel_capacity[0]
        assert selected.call_args.kwargs['refuel'].consumption == experiment.consumption[0]
        assert selected.call_args.kwargs['refuel'].full_init == experiment.full_initial_tank[0]
    else:
        assert not {'prices', 'refuel', 'maxCapacity', 'consumption', 'fullinit'} & selected.call_args.kwargs.keys()
    selected.return_value.run.assert_called_once()


def test_registry_contains_specialized_solvers():
    from tsp_pso.algorithms.solver_registry import SOLVER_REGISTRY
    from tsp_pso.algorithms.tsp.tsp_particle_swarm import TSPParticleSwarm
    from tsp_pso.algorithms.tspwr.tspwr_particle_swarm import TSPWRParticleSwarm

    assert SOLVER_REGISTRY['tsp'][0] is TSPParticleSwarm
    assert SOLVER_REGISTRY['tspwr'][0] is TSPWRParticleSwarm


def test_execute_additional_registered_solver(monkeypatch, tmp_path):
    class AdditionalSolver:
        def __init__(self, **kwargs):
            self.options = kwargs
            created.append(self)

        def run(self, **kwargs):
            self.run_options = kwargs

    created = []
    def additional_arguments(prices, full, capacity, consumption):
        return {'custom_option': capacity}

    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'additional', (AdditionalSolver, additional_arguments))
    matrix = np.array([[0, 2], [2, 0]])
    monkeypatch.setattr(runner, '_load_dataset', lambda descriptor, root: (matrix, None))
    experiment = ExperimentConfiguration(
        datasets=('Minas24D',), legacy_label='registry', c1=(2,), excel=False, verbose=True,
    )

    runner.execute(replace(concrete_run(experiment), problem_mode='additional'), output_dir=tmp_path, dataset={})

    assert len(created) == 1
    assert type(created[0]) is AdditionalSolver
    assert created[0].options['matrix'] is matrix
    assert isinstance(created[0].options['config'], PSOConfig)
    assert 'refuel' not in created[0].options
    assert 'refuel_mode' not in created[0].options
    assert created[0].options['custom_option'] == experiment.fuel_capacity[0]
    assert created[0].run_options['optType'] == experiment.operators[0]


def test_unknown_solver_is_rejected_before_writing(tmp_path):
    experiment = ExperimentConfiguration(
        datasets=('Minas24D',), legacy_label='unknown', c1=(2,), excel=False, verbose=True,
    )
    with pytest.raises(KeyError, match='unknown'):
        runner.execute(replace(concrete_run(experiment), problem_mode='unknown'), output_dir=tmp_path, dataset={})
    assert not list(tmp_path.iterdir())
