"""Small SQLite manifest. Unmaterialized plan ordinals are implicitly pending."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from dataclasses import asdict

from .experiment_batch import EXPANSION_VERSION, ROOT, count_runs


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(directory):
    db = sqlite3.connect(Path(directory) / 'manifest.sqlite3', timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def create_batch(plan):
    root = plan.configuration.output_dir.expanduser()
    if not root.is_absolute():
        root = ROOT / root
    identifier = uuid4().hex
    directory = root / 'batches' / identifier
    directory.mkdir(parents=True, exist_ok=False)
    snapshot = dict(batch_id=identifier, created_at=now(), expansion_version=EXPANSION_VERSION,
                    configuration=plan.configuration.to_dict(),
                    datasets=[asdict(item) for item in plan.datasets],
                    total_runs=str(count_runs(plan)))
    with (directory / 'batch.json').open('x', encoding='utf-8') as stream:
        json.dump(snapshot, stream, indent=2)
    with connect(directory) as db:
        db.executescript('''
            CREATE TABLE batch (id TEXT PRIMARY KEY, total TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT,
                ended_at TEXT, error TEXT);
            CREATE TABLE runs (ordinal TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL, configuration TEXT NOT NULL,
                started_at TEXT NOT NULL, ended_at TEXT, output TEXT, error TEXT);
        ''')
        db.execute('INSERT INTO batch(id,total,status,created_at) VALUES(?,?,?,?)',
                   (identifier,snapshot['total_runs'],'pending',snapshot['created_at']))
    return directory


def start_batch(directory):
    with connect(directory) as db:
        cursor = db.execute("UPDATE batch SET status='running', started_at=? WHERE status='pending'", (now(),))
        if cursor.rowcount != 1:
            raise ValueError('Only a new pending batch may be started; resume is not implemented')


def start_run(directory, ordinal, run):
    with connect(directory) as db:
        identifier = db.execute('SELECT id FROM batch').fetchone()['id']
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',
                   (str(ordinal),f'{identifier}-{ordinal}','running',json.dumps(run.to_dict()),now(),None,None,None))


def finish_run(directory, ordinal, status, *, output=None, error=None):
    with connect(directory) as db:
        db.execute('UPDATE runs SET status=?, ended_at=?, output=?, error=? WHERE ordinal=? AND status=?',
                   (status,now(),str(output) if output is not None else None,error,str(ordinal),'running'))


def finish_batch(directory, status, error=None):
    with connect(directory) as db:
        db.execute('UPDATE batch SET status=?, ended_at=?, error=?', (status,now(),error))


def mark_interrupted(directory, reason='Execution interrupted before completion was confirmed'):
    """Call only after the owning process has stopped, or from that process."""
    with connect(directory) as db:
        db.execute("UPDATE runs SET status='interrupted', ended_at=?, error=? WHERE status='running'", (now(),reason))
        db.execute("UPDATE batch SET status='interrupted', ended_at=?, error=? WHERE status IN ('pending','running')",
                   (now(),reason))


def batch_status(directory):
    with connect(directory) as db:
        batch = dict(db.execute('SELECT * FROM batch').fetchone())
        counts = {row['status']: row['n'] for row in db.execute('SELECT status,COUNT(*) AS n FROM runs GROUP BY status')}
        active = db.execute("SELECT ordinal,configuration FROM runs WHERE status='running' LIMIT 1").fetchone()
    batch['total'] = int(batch['total'])
    batch['counts'] = {state: counts.get(state, 0) for state in ('running','succeeded','failed','interrupted')}
    batch['counts']['pending'] = batch['total'] - sum(counts.values())
    batch['current'] = json.loads(active['configuration']) if active else None
    batch['ordinal'] = int(active['ordinal']) if active else None
    return batch
