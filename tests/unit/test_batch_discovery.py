import sqlite3

from tsp_pso.experiments.batch_store import discover_batches


def test_discovery_is_read_only_and_retains_invalid_entries(batch_artifacts):
    good, _ = batch_artifacts()
    bad, _ = batch_artifacts(completed=False)
    (bad/'manifest.sqlite3').unlink()
    before = {p:p.read_bytes() for p in good.rglob('*') if p.is_file()}
    items = {i['directory']:i for i in discover_batches(good.parent)}
    assert items[good]['status']=='succeeded' and items[good]['completed']==2
    assert items[bad]['status']=='unavailable'
    assert not (bad/'manifest.sqlite3').exists()
    assert all(p.read_bytes()==content for p,content in before.items())


def test_discovery_lists_paused_and_interrupted(batch_artifacts):
    directory, _ = batch_artifacts(completed=False)
    with sqlite3.connect(directory/'manifest.sqlite3') as db:
        db.execute("UPDATE batch SET status='paused'")
    assert discover_batches(directory)[0]['status']=='paused'


def test_discovery_orders_creation_instants_not_paths_or_modification_times(tmp_path, monkeypatch):
    import os

    from tsp_pso.experiments import batch_store
    from tsp_pso.experiments.experiment_batch import compile_plan
    from tsp_pso.experiments.experiment_config import ExperimentConfiguration

    directories = []
    for index, date in enumerate(('2026-11-21T11:00:00+02:00',
                                  '2026-11-21T10:00:00+00:00',
                                  '2026-11-21T08:00:00+00:00')):
        monkeypatch.setattr(batch_store, 'now', lambda date=date: date)
        directory = batch_store.create_batch(compile_plan(ExperimentConfiguration(
            datasets=('bays29',), output_dir=tmp_path, name=str(index))))
        directories.append(directory)
        os.utime(directory / 'manifest.sqlite3', (index + 1, index + 1))
    before = {p: p.read_bytes() for d in directories for p in d.iterdir()}
    items = discover_batches(tmp_path)
    assert [item['directory'] for item in items] == [directories[1], directories[0], directories[2]]
    assert all(p.read_bytes() == content for p, content in before.items())


def test_same_second_batches_sort_by_creation_not_collision_suffix(tmp_path, monkeypatch):
    from tsp_pso.experiments import batch_store
    from tsp_pso.experiments.experiment_batch import compile_plan
    from tsp_pso.experiments.experiment_config import ExperimentConfiguration

    plan = compile_plan(ExperimentConfiguration(datasets=('bays29',), output_dir=tmp_path))
    directories = []
    for microsecond in range(11):
        date = f'2026-11-21T10:35:12.{microsecond:06d}+00:00'
        monkeypatch.setattr(batch_store, 'now', lambda date=date: date)
        directories.append(batch_store.create_batch(plan))
    assert directories[-1].name.endswith('__11')
    assert [item['directory'] for item in discover_batches(tmp_path)] == directories[::-1]
