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
