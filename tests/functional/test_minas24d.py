"""Regression for the Minas24D preset using its real configuration and workbook."""
from functools import partial
from multiprocessing import get_context

import numpy as np
import pytest
from conftest import assert_permutation, concrete_run

import tsp_pso.infrastructure.executors.particle_executor as executor_module
from tsp_pso.algorithms.tsp.tsp_particle_swarm import TSPParticleSwarm
from tsp_pso.algorithms.tspwr.tspwr_particle_swarm import TSPWRParticleSwarm
from tsp_pso.application import runner
from tsp_pso.experiments.experiment_batch import load_presets
from tsp_pso.experiments.experiment_config import (
    ExperimentConfiguration,
    RepetitionSpec,
)
from tsp_pso.infrastructure.experiment_options import load_catalog_options

pytestmark = pytest.mark.functional


def test_minas24d_preset_finds_known_optimum(monkeypatch, tmp_path):
    experiment = load_presets()[7]
    # Pin the preset configuration so future edits cannot silently change this case.
    assert experiment == ExperimentConfiguration(
        name='Minas24D: individual', datasets=('Minas24D',), legacy_label='individual', c1=(1200,),
        particles=(8,), operators=(10,), minimum_reset_probability=(0.2,), maximum_reset_probability=(0.8,),
        ring=(False,), full_initial_tank=(True,), repetitions=RepetitionSpec(1, 1), excel=True,
        problem_modes=('tsp',), legacy_style='standard', fuel_capacity=(150.0,), consumption=(7.0,),
        permutation_reset=(True,), k=(10,), verbose=True,
    )
    assert load_catalog_options()['datasets']['Minas24D'] == {
        'filename': 'Ottoni/Minas24D.xlsx', 'format': 'excel',
        'source': 'Ottoni et al. (2022)', 'problem_types': ['tsp', 'tspwr'],
    }

    # The runner has no seed and uses the default Pool size. One real
    # spawned worker with an explicit seed removes task scheduling and inherited
    # RNG state as sources of variation. Seed 7 also controls swarm initialization.
    seed = 7
    np.random.seed(seed)
    monkeypatch.setattr(
        executor_module, 'Pool',
        partial(get_context('spawn').Pool, processes=1,
                initializer=np.random.seed, initargs=(seed,)),
    )

    created_solvers = []

    def capture_solver(**kwargs):
        # Retain the real instance for assertions; execute() discards run's return.
        solver = TSPParticleSwarm(**kwargs)
        created_solvers.append(solver)
        return solver

    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tsp', (capture_solver, runner.SOLVER_REGISTRY['tsp'][1]))
    run_directory = runner.execute(concrete_run(experiment), output_dir=tmp_path,
                                   dataset=load_catalog_options()['datasets'][experiment.datasets[0]])

    assert len(created_solvers) == 1
    solver = created_solvers[0]
    assert type(solver) is TSPParticleSwarm
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
    workbook = run_directory / 'Minas24D_True_8_1200_10_10_0.2_0.8_1.xlsx'
    assert workbook.is_file()


def test_minas24d_refuel_ring_finds_known_best_cost(monkeypatch, tmp_path):
    from dataclasses import replace

    fuel_experiment = next(
        experiment for experiment in load_presets()
        if experiment.datasets[0] == 'Minas24D'
        and experiment.legacy_label == 'circuit and initial tank'
    )
    # Select one real fuel-sweep configuration and run it once with a fixed seed.
    experiment = replace(
        fuel_experiment, ring=(True,), full_initial_tank=(False,),
        repetitions=RepetitionSpec(1, 1),
    )
    assert experiment == ExperimentConfiguration(
        name='Minas24D: circuit and initial tank', datasets=('Minas24D',),
        legacy_label='circuit and initial tank', c1=(1200,), particles=(8,), operators=(10,),
        minimum_reset_probability=(0.2,), maximum_reset_probability=(0.8,), ring=(True,),
        full_initial_tank=(False,), repetitions=RepetitionSpec(1, 1), excel=True, problem_modes=('tspwr',),
        legacy_style='fuel', fuel_capacity=(150.0,), consumption=(7.0,), permutation_reset=(True,), k=(10,),
        analysis_output='Analysis_Minas24D.xlsx', verbose=False,
    )
    assert load_catalog_options()['datasets']['Minas24D'] == {
        'filename': 'Ottoni/Minas24D.xlsx', 'format': 'excel',
        'source': 'Ottoni et al. (2022)', 'problem_types': ['tsp', 'tspwr'],
    }

    # Seed 1 reproduces the reference cost. Seed both swarm initialization and
    # one real spawned worker to remove scheduling-dependent random sequences.
    seed = 1
    np.random.seed(seed)
    monkeypatch.setattr(
        executor_module, 'Pool',
        partial(get_context('spawn').Pool, processes=1,
                initializer=np.random.seed, initargs=(seed,)),
    )

    created_solvers = []

    def capture_solver(**kwargs):
        # Preserve the real solver and retain its state after execute() returns.
        solver = TSPWRParticleSwarm(**kwargs)
        created_solvers.append(solver)
        return solver

    monkeypatch.setitem(runner.SOLVER_REGISTRY, 'tspwr', (capture_solver, runner.SOLVER_REGISTRY['tspwr'][1]))
    # execute() loads both coordinates and fuel prices from the repository workbook.
    run_directory = runner.execute(concrete_run(experiment), output_dir=tmp_path,
                                   dataset=load_catalog_options()['datasets'][experiment.datasets[0]])

    assert len(created_solvers) == 1
    solver = created_solvers[0]
    assert type(solver) is TSPWRParticleSwarm
    assert solver.distance_matrix.shape == (24, 24)
    assert solver.prices.shape == (24,)
    assert solver.ring_mode is True
    assert solver.fullinit is False
    assert solver.max_steps == 1200 * 24
    assert solver.cur_steps > solver.max_steps
    route = solver.global_best[0]
    assert_permutation(route, 24)

    # Compare fuel cost, not distance, the shifted objective, or a specific route.
    # The reference is rounded to six decimals, so use an absolute tolerance only.
    cost = solver._calculate_refuel(route)
    assert cost == pytest.approx(1426.297870, rel=0, abs=1e-6)
    assert solver.f_global_best[0] == pytest.approx(solver._objective(route))

    workbook = run_directory / 'Minas24D_True_8_1200_10_True_False_1.xlsx'
    assert workbook.is_file()
