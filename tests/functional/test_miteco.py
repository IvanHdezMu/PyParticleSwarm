"""End-to-end compatibility of the saved MITECO JSON with real refuel execution."""

from functools import partial
from multiprocessing import get_context

import numpy as np
import pytest

from conftest import assert_permutation
from tsp_pso import runner
import tsp_pso.solver as solver_module

pytestmark = pytest.mark.functional


def test_miteco_json_runs_in_refuel_mode(monkeypatch, tmp_path):
    # Register only for this test; use the committed dataset without regeneration.
    monkeypatch.setitem(runner.DATASETS, 'MITECO_Madrid20', {
        'filename': 'MITECO_Spain/Comunidad de Madrid_20_seed42.json',
        'format': 'json',
    })
    matrix, prices = runner.load_dataset('MITECO_Madrid20')
    assert matrix.shape == (20, 20)
    assert prices.shape == (20,)
    assert np.all(np.isfinite(matrix))
    assert np.all(np.isfinite(prices))

    # Seed initialization and one real spawned worker independently of scheduling.
    np.random.seed(42)
    monkeypatch.setattr(
        solver_module, 'Pool',
        partial(get_context('spawn').Pool, processes=1,
                initializer=np.random.seed, initargs=(42,)),
    )
    created_solvers = []

    def capture_solver(**kwargs):
        solver = solver_module.ParticleSwarm_VarOptMultiprocess(**kwargs)
        created_solvers.append(solver)
        return solver

    monkeypatch.setattr(runner, 'ParticleSwarm_VarOptMultiprocess', capture_solver)
    experiment = runner.Experiment(
        dataset='MITECO_Madrid20', label='JSON refuel compatibility',
        particles=(4,), steps=(2,), opts=(3,), rings=(True,), full_tanks=(False,),
        repetitions=range(1, 2), refuel=True, max_capacity=150.0, consumption=7.0,
        permut_reset=False, k=3, excel=False, verbose=False,
    )
    runner.execute(experiment, output_dir=tmp_path)

    assert len(created_solvers) == 1
    solver = created_solvers[0]
    assert solver.refuel_mode is True
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
