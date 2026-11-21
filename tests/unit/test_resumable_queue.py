"""Materialized queues preserve effective inputs without re-expansion."""
import json
from unittest.mock import Mock

import pytest

from tsp_pso.experiments import batch_store as store
from tsp_pso.experiments.experiment_batch import compile_plan, iterate_runs
from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec


def test_queue_has_original_order_and_effective_values(tmp_path, monkeypatch):
    plan = compile_plan(ExperimentConfiguration(datasets=('bays29',), operators=(10,15),
        k=(3,7), permutation_reset=(False,), reset_threshold_divisor=(321,17),
        repetitions=RepetitionSpec(2,23), output_dir=tmp_path))
    expected = [r.to_dict() for r in iterate_runs(plan)]
    directory = store.create_batch(plan)
    monkeypatch.setattr(store, 'iterate_runs', Mock(side_effect=AssertionError('expansion')))
    monkeypatch.setattr(store, 'count_runs', Mock(side_effect=AssertionError('count expansion')))
    _, batch, rows = store.read_batch(directory)
    assert batch['manifest_version'] == 2
    assert [json.loads(r['configuration']) for r in rows] == expected
    assert all(r['status']=='pending' and r['started_at'] is None for r in rows)
    assert [r['repetition_id'] for r in expected] == [23,24,23,24,23,24]
    assert all(r['legacy_values']['reset_threshold_divisor']==1000 for r in expected)


def test_preparation_failure_never_publishes_partial_batch(tmp_path, monkeypatch):
    plan = compile_plan(ExperimentConfiguration(datasets=('bays29',), output_dir=tmp_path))
    def broken(plan):
        yield next(iterate_runs(plan))
        raise OSError('disk failure')
    monkeypatch.setattr(store, 'iterate_runs', broken)
    with pytest.raises(OSError, match='disk failure'):
        store.create_batch(plan)
    assert list((tmp_path/'batches').iterdir()) == []
