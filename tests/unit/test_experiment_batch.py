"""Pure expansion and preset compatibility; no dataset payloads are read."""
from collections import Counter
from dataclasses import replace
from itertools import islice
import pytest

from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec
from tsp_pso.experiments.experiment_batch import (
    DatasetDescriptor, compile_plan, count_runs, iterate_runs, load_presets, preview_runs,
)
from tsp_pso.application import runner

pytestmark = pytest.mark.unit
CATALOG = tuple(DatasetDescriptor(n, n+'.json', 'json', 'test', ('tsp', 'tspwr')) for n in ('a', 'b'))


def plan(**kwargs):
    return compile_plan(ExperimentConfiguration(**{'datasets': ('a',), **kwargs}), CATALOG)


@pytest.mark.parametrize('operators', [(10,), (15,), (10, 15), (1, 4, 5, 12, 21)])
@pytest.mark.parametrize('modes', [('tsp',), ('tspwr',), ('tsp', 'tspwr')])
@pytest.mark.parametrize('reset', [(False,), (True,), (False, True)])
def test_count_matches_iterator(operators, modes, reset):
    p = plan(operators=operators, problem_modes=modes, permutation_reset=reset,
             k=(10, 1000, 1000000), particles=(4, 8), c1=(2, 3), ring=(False, True),
             minimum_reset_probability=(0, .2), full_initial_tank=(False, True),
             primary_operator_share=(.2, .5), repetitions=RepetitionSpec(2, 17))
    assert count_runs(p) == sum(1 for _ in iterate_runs(p))


def test_inactive_dimensions_and_order():
    p = plan(datasets=('b', 'a'), operators=(10, 15), k=(5, 10, 20),
             particles=(8, 4), c1=(3, 2), ring=(False, True),
             permutation_reset=(False,), fuel_capacity=(100, 200),
             minimum_reset_probability=(.2, .4), repetitions=RepetitionSpec(2, 6))
    runs = list(iterate_runs(p))
    assert len(runs) == 2 * 4 * 2 * 2 * 2 * 2
    assert [r.repetition_id for r in runs[:4]] == [6, 7, 6, 7]
    assert [(r.particles, r.c1, r.ring) for r in runs[:4]] == [(8,3,False)]*2 + [(8,3,True)]*2
    assert runs[0].dataset == 'b' and runs[-1].dataset == 'a'
    assert all(r.k is None for r in runs if r.operator == 10)
    assert all(r.fuel_capacity is None and r.minimum_reset_probability is None for r in runs)
    assert list(iterate_runs(p)) == runs


def test_huge_repetitions_and_values_are_lazy():
    huge = 10**100
    p = plan(particles=(huge,), c1=(huge,), operators=(15,), k=(10,1000,1000000),
             repetitions=RepetitionSpec(huge, 17))
    assert count_runs(p) == 3 * huge
    assert len(preview_runs(p, 3)) == 3
    assert [r.repetition_id for r in islice(iterate_runs(p), 3)] == [17,18,19]
    for k in (10, 1000, 1000000):
        assert next(iterate_runs(plan(operators=(15,), k=(k,)))).k == k


def test_metadata_compatibility():
    with pytest.raises(ValueError, match='Unknown dataset'):
        plan(datasets=('missing',))
    c = ExperimentConfiguration(datasets=('berlin52',), problem_modes=('tspwr',))
    with pytest.raises(ValueError, match='does not support'):
        compile_plan(c)


def test_warmup_is_conditional():
    assert count_runs(plan(verbose=False, excel=False, progress_warmup_multiplier=(0,5))) == 1
    assert count_runs(plan(verbose=True, excel=False, progress_warmup_multiplier=(0,5))) == 2


def test_all_legacy_presets_preserve_every_argument():
    presets = load_presets()
    counts = [count_runs(compile_plan(p)) for p in presets]
    assert counts == [1]*10 + [270,180,80,120,50,4,5,120,120,120,120,10]
    assert sum(counts) == 1209
    for old, new in zip(runner.EXPERIMENTS, presets):
        expected, actual = Counter(), Counter()
        for n,c1,opt,minimum,maximum,ring,full,number in old.configurations():
            expected[(old.dataset,old.refuel,n,c1,opt,minimum,maximum,ring,full,number,
                      old.k,old.permut_reset,old.max_capacity,old.consumption,
                      old.reset_threshold_divisor,old.primary_operator_share,
                      old.progress_warmup_multiplier,old.verbose,old.excel)] += 1
        for r in iterate_runs(compile_plan(new)):
            e = dict(r.legacy_values)
            actual[(r.dataset,r.problem_mode=='tspwr',r.particles,r.c1,r.operator,
                    e['minimum_reset_probability'],e['maximum_reset_probability'],r.ring,
                    e['full_initial_tank'],r.repetition_id,e['k'],r.permutation_reset,
                    e['fuel_capacity'],e['consumption'],e['reset_threshold_divisor'],
                    e['primary_operator_share'],e['progress_warmup_multiplier'],r.verbose,r.excel)] += 1
        assert actual == expected
        assert new.legacy_style == old.style and new.analysis_output == old.analysis_output
        assert replace(new, k=(123456,)).k == (123456,)
