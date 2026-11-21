"""Pure expansion and preset compatibility; no dataset payloads are read."""
from tsp_pso.infrastructure.experiment_options import load_run_options
from tsp_pso.experiments.experiment import build_experiments
from collections import Counter
from dataclasses import fields, replace
from itertools import islice
import pytest

from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec
from tsp_pso.experiments.experiment_batch import (
    CONDITIONAL, DEFAULTS, ConcreteRunConfiguration,
    DatasetDescriptor, compile_plan, count_runs, iterate_runs, load_presets,
)

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
    assert [r.repetition_id for r in islice(iterate_runs(p), 3)] == [17,18,19]
    for k in (10, 1000, 1000000):
        assert next(iterate_runs(plan(operators=(15,), k=(k,)))).k == k


def test_metadata_compatibility():
    with pytest.raises(ValueError, match='Unknown dataset'):
        plan(datasets=('missing',))
    c = ExperimentConfiguration(datasets=('berlin52',), problem_modes=('tspwr',))
    with pytest.raises(ValueError, match='does not support'):
        compile_plan(c)


@pytest.mark.parametrize('verbose,excel,expected', [
    (False, False, [(None, 5)]),
    (False, True, [(13, 13), (2, 2)]),
    (True, False, [(13, 13), (2, 2)]),
    (True, True, [(13, 13), (2, 2)]),
])
def test_warmup_is_conditional(verbose, excel, expected):
    p = plan(verbose=verbose, excel=excel, progress_warmup_multiplier=(13, 2))
    runs = list(iterate_runs(p))
    assert count_runs(p) == len(expected)
    assert [(r.progress_warmup_multiplier, dict(r.legacy_values)['progress_warmup_multiplier'])
            for r in runs] == expected


def test_all_legacy_presets_preserve_every_argument():
    presets = load_presets()
    counts = [count_runs(compile_plan(p)) for p in presets]
    assert counts == [1]*10 + [270,180,80,120,50,4,5,120,120,120,120,10]
    assert sum(counts) == 1209
    for old, new in zip(build_experiments(load_run_options()), presets):
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


@pytest.mark.parametrize('name,requested,fallback,inactive_context', [
    ('k', (17, 3), 10, {'operators': (10,)}),
    ('primary_operator_share', (.73, .11), .2, {'operators': (10,)}),
    ('minimum_reset_probability', (.13, .07), .2, {'permutation_reset': (False,)}),
    ('maximum_reset_probability', (.91, .67), .8, {'permutation_reset': (False,)}),
    ('reset_threshold_divisor', (321, 17), 1000, {'permutation_reset': (False,)}),
    ('fuel_capacity', (123.5, 91), 150.0, {'problem_modes': ('tsp',)}),
    ('consumption', (4.25, 3), 7.0, {'problem_modes': ('tsp',)}),
    ('full_initial_tank', (True, False), False, {'problem_modes': ('tsp',)}),
    ('progress_warmup_multiplier', (13, 2), 5, {'verbose': False, 'excel': False}),
])
@pytest.mark.parametrize('active,multiple', [(True, False), (True, True),
                                           (False, False), (False, True)])
def test_conditional_requested_and_effective_values(name, requested, fallback,
                                                  inactive_context, active, multiple):
    requested = requested if multiple else requested[:1]
    context = dict(problem_modes=('tspwr',), operators=(15,), permutation_reset=(True,),
                   verbose=True, excel=True)
    if not active:
        context.update(inactive_context)
    p = plan(**context, **{name: requested})
    before = p.configuration.to_dict()
    runs = list(iterate_runs(p))
    expected = requested if active else (fallback if multiple else requested[0],)
    assert count_runs(p) == len(runs) == len(expected)
    assert p.configuration.to_dict() == before
    assert getattr(p.configuration, name) == requested
    for run, value in zip(runs, expected):
        assert getattr(run, name) == (value if active else None)
        effective = dict(run.legacy_values)
        assert effective[name] == value
        assert type(effective[name]) is type(value)
        saved = run.to_dict()
        assert saved[name] == (value if active else None)
        assert saved['legacy_values'][name] == value
        assert type(saved['legacy_values'][name]) is type(value)


def test_complete_conditional_sequence_and_repetition_order():
    # All nine axes are active. Expected block lengths below are fixed evidence
    # of the ordering, independent of CONDITIONAL and the expansion helpers.
    p = plan(problem_modes=('tspwr',), operators=(15,), permutation_reset=(True,),
             k=(17, 3), primary_operator_share=(.73, .11),
             minimum_reset_probability=(.13, .07), maximum_reset_probability=(.91, .67),
             reset_threshold_divisor=(321, 17), fuel_capacity=(123.5, 91),
             consumption=(4.25, 3), full_initial_tank=(True, False),
             progress_warmup_multiplier=(13, 2), repetitions=RepetitionSpec(2, 17))
    expected = [
        ((17, 3)[i // 512 % 2], (.73, .11)[i // 256 % 2],
         (.13, .07)[i // 128 % 2], (.91, .67)[i // 64 % 2],
         (321, 17)[i // 32 % 2], (123.5, 91)[i // 16 % 2],
         (4.25, 3)[i // 8 % 2], (True, False)[i // 4 % 2],
         (13, 2)[i // 2 % 2], 17 + i % 2)
        for i in range(1024)
    ]
    runs = list(iterate_runs(p))
    assert count_runs(p) == 1024
    assert [(r.k, r.primary_operator_share, r.minimum_reset_probability,
             r.maximum_reset_probability, r.reset_threshold_divisor, r.fuel_capacity,
             r.consumption, r.full_initial_tank, r.progress_warmup_multiplier, r.repetition_id)
            for r in runs] == expected
    assert [tuple(value for _, value in r.legacy_values) + (r.repetition_id,)
            for r in runs] == expected


def test_conditional_fields_defaults_and_concrete_model_agree():
    expected = ('k', 'primary_operator_share', 'minimum_reset_probability',
                'maximum_reset_probability', 'reset_threshold_divisor', 'fuel_capacity',
                'consumption', 'full_initial_tank', 'progress_warmup_multiplier')
    assert CONDITIONAL == expected
    assert set(DEFAULTS) == set(expected)
    # The optional scientific fields must be exactly the conditional fields;
    # legacy_label and analysis_output are optional presentation metadata.
    optional_science = {f.name for f in fields(ConcreteRunConfiguration)
                        if type(None) in getattr(f.type, '__args__', ())
                        and f.name not in ('legacy_label', 'analysis_output')}
    assert optional_science == set(expected)
    assert set(expected) <= {f.name for f in fields(ExperimentConfiguration)}
