"""Small shared fixtures; the solver source is left unchanged."""

import numpy as np
import pytest

from tsp_pso.algorithms.core.pso_config import PSOConfig
from tsp_pso.algorithms.tspwr.refuel_config import RefuelConfig
from tsp_pso.algorithms.tsp.tsp_particle_swarm import TSPParticleSwarm
from tsp_pso.algorithms.tspwr.tspwr_particle_swarm import TSPWRParticleSwarm


@pytest.fixture(autouse=True)
def fixed_random_seed():
    state = np.random.get_state()
    np.random.seed(7)
    yield
    np.random.set_state(state)


@pytest.fixture
def distance_matrix():
    # Row minima: 2 + 2 + 3 + 4 = 11; maxima: 9 + 8 + 9 + 8 = 34.
    return np.array([[0, 2, 9, 7], [2, 0, 3, 8],
                     [9, 3, 0, 4], [7, 8, 4, 0]])


@pytest.fixture
def make_solver(distance_matrix):
    def make(*, refuel_mode=False, **kwargs):
        options = dict(N=4, c1=2, distance_matrix=distance_matrix.copy())
        options.update(kwargs)
        matrix = options.pop('distance_matrix')
        fuel = {}
        if refuel_mode:
            fuel = dict(
                prices=options.pop('prices', np.array([4., 2., 3., 5.])),
                refuel=RefuelConfig(
                    max_capacity=options.pop('maxCapacity', 20),
                    consumption=options.pop('consumption', 2),
                    full_init=options.pop('fullinit', False)))
        for old, new in [('resetThresholdDivisor', 'reset_threshold_divisor'),
                         ('primaryOperatorShare', 'primary_operator_share'),
                         ('progressWarmupMultiplier', 'progress_warmup_multiplier')]:
            if old in options:
                options[new] = options.pop(old)
        solver_class = TSPWRParticleSwarm if refuel_mode else TSPParticleSwarm
        return solver_class(matrix=matrix, config=PSOConfig(**options), **fuel)
    return make


@pytest.fixture
def solver(make_solver):
    return make_solver()


def assert_permutation(route, size):
    assert route.shape == (size,)
    assert np.issubdtype(route.dtype, np.integer)
    np.testing.assert_array_equal(np.sort(route), np.arange(size))


@pytest.fixture
def batch_artifacts(tmp_path):
    """Small saved batches and a workbook-producing run stub; no solver calls."""
    import pandas as pd
    from tsp_pso.experiments.batch_executor import to_legacy_experiment
    from tsp_pso.experiments.batch_store import (
        create_batch, start_batch, start_run, finish_run, finish_batch,
    )
    from tsp_pso.experiments.experiment_batch import DatasetDescriptor, compile_plan, iterate_runs
    from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec
    from tsp_pso.experiments.result_naming import result_filename
    from tsp_pso.infrastructure.run_storage import create_run_directory

    def make(*, completed=True, history=None, **overrides):
        options = dict(datasets=('sample',), particles=(2,), c1=(2,), operators=(3,),
                       repetitions=RepetitionSpec(2, 17), output_dir=tmp_path)
        options.update(overrides)
        configuration = ExperimentConfiguration(**options)
        catalog = tuple(DatasetDescriptor(name, 'not-needed.json', 'json', 'test',
                                         ('tsp', 'tspwr')) for name in configuration.datasets)
        plan = compile_plan(configuration, catalog)
        directory = create_batch(plan)

        def write(run, output, descriptor):
            experiment = to_legacy_experiment(run)
            destination = create_run_directory(experiment, output)
            if run.excel:
                samples = (history(run) if history is not None else
                           [[9, 20 + run.repetition_id], [7, 10 + run.repetition_id],
                            [3, 10 + run.repetition_id]])
                pd.DataFrame(samples, columns=['Step', 'Result']).to_excel(
                    destination / result_filename(experiment, next(experiment.configurations())),
                    index=False)
            return destination

        if completed:
            start_batch(directory)
            for ordinal, run in enumerate(iterate_runs(plan), 1):
                start_run(directory, ordinal, run)
                output = write(run, directory / 'runs' / str(ordinal), None)
                finish_run(directory, ordinal, 'succeeded', output=output)
            finish_batch(directory, 'succeeded')
        return directory, write
    return make


@pytest.fixture
def completed_batch(batch_artifacts):
    return lambda **kwargs: batch_artifacts(**kwargs)[0]
