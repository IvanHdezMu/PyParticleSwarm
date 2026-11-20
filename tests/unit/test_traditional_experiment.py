"""Compatibility of the extracted traditional experiment model."""

from copy import copy
from multiprocessing import get_all_start_methods, get_context
import pickle

import pytest

from tsp_pso.application import runner
from tsp_pso.experiments.experiment import Experiment


@pytest.mark.unit
def test_old_module_pickle_remains_loadable():
    assert runner.Experiment is Experiment
    experiment = Experiment(dataset='sample', label='pickle', steps=(2,),
                            repetitions=range(3, 9, 2))
    current = pickle.dumps(experiment, protocol=0)
    new_name = b'ctsp_pso.experiments.experiment\nExperiment\n'
    assert new_name in current
    previous = current.replace(new_name, b'ctsp_pso.application.runner\nExperiment\n')
    for payload in (current, previous):
        restored = pickle.loads(payload)
        assert type(restored) is Experiment
        assert restored == experiment
        assert list(restored.configurations()) == list(experiment.configurations())


@pytest.mark.functional
@pytest.mark.parametrize('method', [m for m in ('spawn', 'forkserver')
                                    if m in get_all_start_methods()])
def test_experiment_round_trip_through_worker(method):
    experiment = Experiment(dataset='sample', label='worker', steps=(2, 3),
                            particles=(4, 8), repetitions=range(3, 9, 2))
    with get_context(method).Pool(processes=1) as pool:
        restored, = pool.map(copy, [experiment])
    assert type(restored) is Experiment
    assert restored == experiment
    assert restored.count == experiment.count == 12
    assert list(restored.configurations()) == list(experiment.configurations())
