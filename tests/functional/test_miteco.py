"""End-to-end compatibility of the saved MITECO JSON with real refuel execution."""
from functools import partial
from multiprocessing import get_context

import numpy as np
import pytest
from conftest import assert_permutation, concrete_run

import tsp_pso.infrastructure.executors.particle_executor as executor_module
from tsp_pso.algorithms.tspwr.tspwr_particle_swarm import TSPWRParticleSwarm
from tsp_pso.application import runner
from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)
from tsp_pso.infrastructure.dataset_reader import load_dataset

pytestmark = pytest.mark.functional


def test_miteco_json_runs_in_refuel_mode(monkeypatch, tmp_path):
    # Register only for this test; use the committed dataset without regeneration.
    dataset = {
        'filename': 'MITECO_Spain/Comunidad de Madrid_20_seed42.json',
        'format': 'json',
    }
    matrix, prices = load_dataset(dataset, runner.ROOT / 'datasets')
    assert matrix.shape == (20, 20)
    assert prices.shape == (20,)
    assert np.all(np.isfinite(matrix))
    assert np.all(np.isfinite(prices))

    # Seed initialization and one real spawned worker independently of scheduling.
    np.random.seed(42)
    monkeypatch.setattr(
        executor_module, 'Pool',
        partial(get_context('spawn').Pool, processes=1,
                initializer=np.random.seed, initargs=(42,)),
    )
    created_solvers = []

    def capture_solver(**kwargs):
        solver = TSPWRParticleSwarm(**kwargs)
        created_solvers.append(solver)
        return solver

    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (capture_solver, runner.SOLVER_REGISTRY['tspwr'][1]))
    experiment = ExperimentConfiguration(
        datasets=('MITECO_Madrid20',), legacy_label='JSON refuel compatibility', particles=(4,), c1=(2,),
        operators=(3,), ring=(True,), full_initial_tank=(False,), repetitions=RepetitionSpec(1, 1),
        problem_modes=('tspwr',), fuel_capacity=(150.0,), consumption=(7.0,), permutation_reset=(False,),
        k=(3,), excel=False, verbose=False,
    )
    runner.execute(concrete_run(experiment), output_dir=tmp_path, dataset=dataset)

    assert len(created_solvers) == 1
    solver = created_solvers[0]
    assert type(solver) is TSPWRParticleSwarm
    assert solver.ring_mode is True
    assert solver.fullinit is False
    np.testing.assert_array_equal(solver.distance_matrix, matrix)
    np.testing.assert_array_equal(solver.prices, prices)
    assert solver.max_steps == 2 * 20
    assert solver.cur_steps > solver.max_steps
    route = solver.global_best[0]
    assert_permutation(route, 20)
    cost = solver._calculate_refuel(route)
    objective = solver._objective(route)
    assert np.isfinite(cost)
    assert np.isfinite(objective)
    assert solver.f_global_best[0] == pytest.approx(objective)
    print(f'MITECO final refuel cost: {cost:.12f}; objective: {objective:.12f}')
