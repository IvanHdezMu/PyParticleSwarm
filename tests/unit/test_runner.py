"""Focused checks for solver parameter forwarding from experiment configuration."""

from unittest.mock import Mock

import numpy as np
import pytest

from tsp_pso.application import runner
from tsp_pso.algorithms.solver_config import PSOConfig, RefuelConfig

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('override', [None, 1])
def test_reset_threshold_divisor_config_and_forwarding(monkeypatch, tmp_path, override):
    options = runner.load_run_options()
    assert options['defaults']['reset_threshold_divisor'] == 1000
    options['experiments'] = [options['experiments'][0]]
    options['experiments'][0]['excel'] = False
    if override is not None:
        options['experiments'][0]['reset_threshold_divisor'] = override
    experiment, = runner.build_experiments(options)
    assert experiment.reset_threshold_divisor == (1000 if override is None else override)

    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.assert_called_once()
    assert factory.call_args.kwargs['config'].reset_threshold_divisor == experiment.reset_threshold_divisor
    factory.return_value.run.assert_called_once()


@pytest.mark.parametrize('override', [None, 0.5])
def test_primary_operator_share_config_and_forwarding(monkeypatch, tmp_path, override):
    options = runner.load_run_options()
    assert options['defaults']['primary_operator_share'] == 0.2
    options['experiments'] = [options['experiments'][0]]
    options['experiments'][0]['excel'] = False
    if override is not None:
        options['experiments'][0]['primary_operator_share'] = override
    experiment, = runner.build_experiments(options)
    assert experiment.primary_operator_share == (0.2 if override is None else override)

    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.assert_called_once()
    assert factory.call_args.kwargs['config'].primary_operator_share == experiment.primary_operator_share
    factory.return_value.run.assert_called_once()


@pytest.mark.parametrize('override', [None, 1])
def test_progress_warmup_multiplier_config_and_forwarding(monkeypatch, tmp_path, override):
    options = runner.load_run_options()
    assert options['defaults']['progress_warmup_multiplier'] == 5
    options['experiments'] = [options['experiments'][0]]
    options['experiments'][0]['excel'] = False
    if override is not None:
        options['experiments'][0]['progress_warmup_multiplier'] = override
    experiment, = runner.build_experiments(options)
    assert experiment.progress_warmup_multiplier == (5 if override is None else override)

    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.assert_called_once()
    assert factory.call_args.kwargs['config'].progress_warmup_multiplier == experiment.progress_warmup_multiplier
    factory.return_value.run.assert_called_once()


def test_existing_experiment_verbose_behavior(monkeypatch, tmp_path):
    assert runner.RUN_OPTIONS['defaults']['verbose'] is True
    assert runner.Experiment(dataset='Minas24D', label='individual', steps=(1200,)).verbose is True
    assert all('verbose' not in dataset for dataset in runner.DATASETS.values())
    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    assert len(runner.EXPERIMENTS) == 22
    for number, experiment in enumerate(runner.EXPERIMENTS, 1):
        # Berlin52 and Bays29 were quiet; the other individual runs were verbose.
        assert experiment.verbose is (3 <= number <= 10)
        factory.reset_mock()
        runner.execute(experiment, output_dir=tmp_path)
        assert factory.return_value.run.call_count == experiment.count
        for call in factory.return_value.run.call_args_list:
            assert call.kwargs['verbose'] is (3 <= number <= 10)


@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('label', ['individual', 'renamed experiment'])
@pytest.mark.parametrize('excel', [False, True])
def test_experiment_verbose_override(monkeypatch, tmp_path, verbose, label, excel):
    options = runner.load_run_options()
    options['defaults']['verbose'] = not verbose
    options['experiments'] = [{
        'dataset': 'berlin52', 'label': label, 'steps': [2],
        'verbose': verbose, 'excel': excel,
    }]
    experiment, = runner.build_experiments(options)
    assert experiment.verbose is verbose
    factory = Mock()
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (factory, runner.SOLVER_REGISTRY['tsp'][1]))
    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (factory, runner.SOLVER_REGISTRY['tspwr'][1]))
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
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
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (matrix, prices))
    experiment = runner.Experiment(
        dataset='Minas24D', label='class selection', steps=(2,), refuel=refuel,
    )

    runner.execute(experiment, output_dir=tmp_path)

    selected, unused = (tspwr_factory, tsp_factory) if refuel else (tsp_factory, tspwr_factory)
    selected.assert_called_once()
    unused.assert_not_called()
    assert 'refuel_mode' not in selected.call_args.kwargs
    assert isinstance(selected.call_args.kwargs['config'], PSOConfig)
    assert selected.call_args.kwargs['matrix'] is matrix
    if refuel:
        assert isinstance(selected.call_args.kwargs['refuel'], RefuelConfig)
        assert selected.call_args.kwargs['prices'] is prices
        assert selected.call_args.kwargs['refuel'].max_capacity == experiment.max_capacity
        assert selected.call_args.kwargs['refuel'].consumption == experiment.consumption
        assert selected.call_args.kwargs['refuel'].full_init == experiment.full_tanks[0]
    else:
        assert not {'prices', 'refuel', 'maxCapacity', 'consumption', 'fullinit'} & selected.call_args.kwargs.keys()
    selected.return_value.run.assert_called_once()


def test_registry_contains_specialized_solvers():
    from tsp_pso.algorithms.solver_registry import SOLVER_REGISTRY
    from tsp_pso.algorithms.tsp_solver import TSPParticleSwarm
    from tsp_pso.algorithms.tspwr_solver import TSPWRParticleSwarm

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
    def additional_arguments(experiment, prices, full):
        return {'custom_option': experiment.label}

    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'additional', (AdditionalSolver, additional_arguments))
    matrix = np.array([[0, 2], [2, 0]])
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (matrix, None))
    experiment = runner.Experiment(dataset='Minas24D', label='registry', steps=(2,))

    runner.execute(experiment, output_dir=tmp_path, problem_type='additional')

    assert len(created) == 1
    assert type(created[0]) is AdditionalSolver
    assert created[0].options['matrix'] is matrix
    assert isinstance(created[0].options['config'], PSOConfig)
    assert 'refuel' not in created[0].options
    assert 'refuel_mode' not in created[0].options
    assert created[0].options['custom_option'] == 'registry'
    assert created[0].run_options['optType'] == experiment.opts[0]


def test_unknown_solver_is_rejected_before_writing(tmp_path):
    experiment = runner.Experiment(dataset='Minas24D', label='unknown', steps=(2,))
    with pytest.raises(KeyError, match='unknown'):
        runner.execute(experiment, output_dir=tmp_path, problem_type='unknown')
    assert not list(tmp_path.iterdir())
