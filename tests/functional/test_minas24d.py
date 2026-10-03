"""Regression for menu option 8 using its real configuration and workbook."""

from functools import partial
from multiprocessing import get_context

import numpy as np
import pytest

from tsp_pso import runner
import tsp_pso.solver as solver_module

from conftest import assert_permutation

pytestmark = pytest.mark.functional


def test_option_8_minas24d_finds_known_optimum(monkeypatch, tmp_path):
    experiment = runner.EXPERIMENTS[7]
    # Pin the menu configuration so future edits cannot silently change this case.
    assert experiment == runner.Experiment(
        dataset='Minas24D', label='individual', steps=(1200,), particles=(8,),
        opts=(10,), minimums=(0.2,), maximums=(0.8,), rings=(False,),
        full_tanks=(True,), repetitions=range(1, 2), excel=True, refuel=False,
        style='standard', max_capacity=150.0, consumption=7.0,
        permut_reset=True, k=10,
    )
    assert runner.DATASETS['Minas24D'] == {
        'filename': 'Minas24D.xlsx', 'format': 'excel', 'verbose': True,
    }

    # The original runner has no seed and uses the default Pool size. One real
    # spawned worker with an explicit seed removes task scheduling and inherited
    # RNG state as sources of variation. Seed 7 also controls swarm initialization.
    seed = 7
    np.random.seed(seed)
    monkeypatch.setattr(
        solver_module, 'Pool',
        partial(get_context('spawn').Pool, processes=1,
                initializer=np.random.seed, initargs=(seed,)),
    )

    created_solvers = []

    def capture_solver(**kwargs):
        # Retain the real instance for assertions; execute() discards run's return.
        solver = solver_module.ParticleSwarm_VarOptMultiprocess(**kwargs)
        created_solvers.append(solver)
        return solver

    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', capture_solver)
    runner.execute(experiment, output_dir=tmp_path)

    assert len(created_solvers) == 1
    solver = created_solvers[0]
    assert solver.distance_matrix.shape == (24, 24)
    assert solver.max_steps == 1200 * 24
    assert solver.cur_steps > solver.max_steps
    route = solver.global_best[0]
    assert_permutation(route, 24)

    # Compare distance, not the shifted objective or one particular optimal route.
    # The supplied reference is rounded to six decimal places; disable relative
    # tolerance to avoid accepting a materially worse route at this distance scale.
    expected_distance = pytest.approx(2581.922429, rel=0, abs=1e-6)
    distance = solver.distance_matrix[route[:-1], route[1:]].sum()
    assert distance == expected_distance
    assert solver._calculate_distance(route) == expected_distance
    assert solver.f_global_best[0] == pytest.approx(solver._objective(route))

    # Keep the original Excel behavior while avoiding writes to repository results.
    configuration, = experiment.configurations()
    workbook = tmp_path / 'Minas24D' / runner.result_filename(experiment, configuration)
    assert workbook.is_file()
