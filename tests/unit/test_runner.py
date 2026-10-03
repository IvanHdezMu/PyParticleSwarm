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
