"""Small SQLite manifest. Unmaterialized plan ordinals are implicitly pending."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from dataclasses import asdict, fields

from ..infrastructure.experiment_options import ROOT
from .experiment_batch import EXPANSION_VERSION, DatasetDescriptor, compile_plan, count_runs
from .experiment_config import ExperimentConfiguration


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(directory, *, create=False, timeout=10):
    """Open an existing manifest; only initial batch creation opts into creation.

    SQLite raises OperationalError if the manifest cannot be opened. URI mode
    rw prevents accidental creation without a separate filesystem check.
    timeout bounds SQLite lock waits for this connection only, in seconds.
    """
    uri = (Path(directory) / 'manifest.sqlite3').absolute().as_uri()
    mode = 'rwc' if create else 'rw'
    db = sqlite3.connect(f'{uri}?mode={mode}', uri=True, timeout=timeout)
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
    with connect(directory, create=True) as db:
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


def mark_interrupted(directory, reason='Execution interrupted before completion was confirmed', *, timeout=10):
    """Call only after the owning process has stopped, or from that process."""
    with connect(directory, timeout=timeout) as db:
        db.execute("UPDATE runs SET status='interrupted', ended_at=?, error=? WHERE status='running'", (now(),reason))
        db.execute("UPDATE batch SET status='interrupted', ended_at=?, error=? WHERE status IN ('pending','running')",
                   (now(),reason))


def batch_status(directory, *, timeout=10):
    with connect(directory, timeout=timeout) as db:
        # sqlite3 does not implicitly begin a transaction for SELECT statements.
        # Keep all three queries on one snapshot; connect commits or rolls back.
        db.execute('BEGIN')
        batch = dict(db.execute('SELECT * FROM batch').fetchone())
        counts = {row['status']: row['n'] for row in db.execute('SELECT status,COUNT(*) AS n FROM runs GROUP BY status')}
        active = db.execute("SELECT ordinal,configuration FROM runs WHERE status='running' LIMIT 1").fetchone()
    batch['total'] = int(batch['total'])
    batch['counts'] = {state: counts.get(state, 0) for state in ('running','succeeded','failed','interrupted')}
    batch['counts']['pending'] = batch['total'] - sum(counts.values())
    batch['current'] = json.loads(active['configuration']) if active else None
    batch['ordinal'] = int(active['ordinal']) if active else None
    return batch


def positive_decimal(value):
    """Read persisted arbitrary-size counts/ordinals without SQLite casts."""
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError(f'Expected a positive decimal string, got {value!r}')
    number = int(value)
    if number < 1 or str(number) != value:
        raise ValueError(f'Invalid count or ordinal: {value!r}')
    return number


def read_batch(directory):
    """Read and validate shared version-one JSON/manifest structure without writes."""
    directory = Path(directory).resolve()
    with (directory / 'batch.json').open(encoding='utf-8') as stream:
        snapshot = json.load(stream)
    if (type(snapshot['expansion_version']) is not int
            or snapshot['expansion_version'] != EXPANSION_VERSION):
        raise ValueError('Unsupported expansion version')
    identifier = snapshot['batch_id']
    if not isinstance(identifier, str) or not identifier:
        raise ValueError('Invalid batch identifier')
    datetime.fromisoformat(snapshot['created_at'])
    requested = snapshot['configuration']
    if set(requested) != {f.name for f in fields(ExperimentConfiguration)}:
        raise ValueError('Incomplete or incompatible batch configuration')
    configuration = ExperimentConfiguration.from_dict(requested)
    catalog = tuple(DatasetDescriptor(**item) for item in snapshot['datasets'])
    for item in catalog:
        if (any(not isinstance(value, str) or not value for value in
                (item.id, item.filename, item.format, item.source))
                or not isinstance(item.problem_types, list) or not item.problem_types
                or any(mode not in ('tsp', 'tspwr') for mode in item.problem_types)):
            raise ValueError('Invalid saved dataset descriptor')
    if len({item.id for item in catalog}) != len(catalog):
        raise ValueError('Duplicate dataset descriptors')
    plan = compile_plan(configuration, catalog)
    total = positive_decimal(snapshot['total_runs'])
    if count_runs(plan) != total:
        raise ValueError('Declared total does not match the saved configuration')

    uri = (directory / 'manifest.sqlite3').as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        batches = [dict(row) for row in db.execute('SELECT id,total,status,created_at,started_at,ended_at,error FROM batch')]
        runs = [dict(row) for row in db.execute('SELECT ordinal,run_id,status,configuration,started_at,ended_at,output,error FROM runs')]
    if len(batches) != 1 or batches[0]['id'] != identifier:
        raise ValueError('Batch identifier mismatch between JSON and manifest')
    batch = batches[0]
    if batch['created_at'] != snapshot['created_at']:
        raise ValueError('Creation timestamp differs between JSON and manifest')
    if positive_decimal(batch['total']) != total:
        raise ValueError('Declared totals disagree between JSON and manifest')
    return plan, batch, runs
