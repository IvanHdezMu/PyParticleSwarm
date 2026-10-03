"""Focused checks for solver parameter forwarding from experiment configuration."""

from unittest.mock import Mock

import numpy as np
import pytest

from tsp_pso import runner

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
    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', factory)
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.assert_called_once()
    assert factory.call_args.kwargs['resetThresholdDivisor'] == experiment.reset_threshold_divisor
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
    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', factory)
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.assert_called_once()
    assert factory.call_args.kwargs['primaryOperatorShare'] == experiment.primary_operator_share
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
    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', factory)
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.assert_called_once()
    assert factory.call_args.kwargs['progressWarmupMultiplier'] == experiment.progress_warmup_multiplier
    factory.return_value.run.assert_called_once()


def test_existing_experiment_verbose_behavior(monkeypatch, tmp_path):
    assert runner.RUN_OPTIONS['defaults']['verbose'] is True
    assert runner.Experiment(dataset='Minas24D', label='individual', steps=(1200,)).verbose is True
    assert all('verbose' not in dataset for dataset in runner.DATASETS.values())
    factory = Mock()
    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', factory)
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    for number, experiment in enumerate(runner.EXPERIMENTS, 1):
        # Berlin52 and Bays29 were quiet; the other individual runs were verbose.
        assert experiment.verbose is (experiment.dataset not in ('berlin52', 'bays29'))
        factory.reset_mock()
        runner.execute(experiment, output_dir=tmp_path)
        assert factory.return_value.run.call_count == experiment.count
        for call in factory.return_value.run.call_args_list:
            assert call.kwargs['verbose'] is (3 <= number <= 10)


@pytest.mark.parametrize('verbose', [False, True])
@pytest.mark.parametrize('label, excel', [('individual', True), ('sweep', True), ('sweep', False)])
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
    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', factory)
    monkeypatch.setattr(runner, 'load_dataset', lambda name: (np.array([[0, 2], [2, 0]]), None))
    runner.execute(experiment, output_dir=tmp_path)
    factory.return_value.run.assert_called_once()
    assert factory.return_value.run.call_args.kwargs['verbose'] is (
        verbose and (label == 'individual' or not excel)
    )
