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
