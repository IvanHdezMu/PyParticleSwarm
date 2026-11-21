"""Small SQLite manifest. Unmaterialized plan ordinals are implicitly pending."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import shutil
from uuid import uuid4
from dataclasses import asdict, fields

from ..infrastructure.experiment_options import ROOT
from .experiment_batch import EXPANSION_VERSION, DatasetDescriptor, compile_plan, count_runs, iterate_runs
from .experiment_config import ExperimentConfiguration


MANIFEST_VERSION = 2
MAX_BATCH_RUNS = 10000


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
    total = count_runs(plan)
    if total > MAX_BATCH_RUNS:
        raise ValueError(f'Resumable batches support at most {MAX_BATCH_RUNS:,} runs; requested {total}')
    root = plan.configuration.output_dir.expanduser()
    if not root.is_absolute():
        root = ROOT / root
    identifier = uuid4().hex
    directory = root / 'batches' / identifier
    temporary = directory.with_name('.preparing-' + identifier)
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        snapshot = dict(batch_id=identifier, created_at=now(), expansion_version=EXPANSION_VERSION,
                        manifest_version=MANIFEST_VERSION,
                        configuration=plan.configuration.to_dict(),
                        datasets=[asdict(item) for item in plan.datasets], total_runs=str(total))
        with (temporary / 'batch.json').open('x', encoding='utf-8') as stream:
            json.dump(snapshot, stream, indent=2)
        with connect(temporary, create=True) as db:
            db.executescript("""
                PRAGMA user_version=2;
                CREATE TABLE batch (id TEXT PRIMARY KEY, total TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT,
                    ended_at TEXT, error TEXT);
                CREATE TABLE runs (ordinal TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL, configuration TEXT NOT NULL,
                    started_at TEXT, ended_at TEXT, output TEXT, error TEXT);
                CREATE TABLE control (id INTEGER PRIMARY KEY CHECK(id=1),
                    pause_requested INTEGER NOT NULL DEFAULT 0, owner TEXT);
                INSERT INTO control(id) VALUES(1);
            """)
            db.execute('INSERT INTO batch(id,total,status,created_at) VALUES(?,?,?,?)',
                       (identifier,str(total),'pending',snapshot['created_at']))
            db.executemany('INSERT INTO runs VALUES(?,?,?,?,NULL,NULL,NULL,NULL)',
                           ((str(i), f'{identifier}-{i}', 'pending', json.dumps(run.to_dict()))
                            for i, run in enumerate(iterate_runs(plan), 1)))
            if db.execute('SELECT COUNT(*) FROM runs').fetchone()[0] != total:
                raise ValueError('Incomplete queue preparation')
        temporary.rename(directory)
    except BaseException:
        shutil.rmtree(temporary)
        raise
    return directory


def start_batch(directory):
    with connect(directory) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('PRAGMA user_version').fetchone()[0] == MANIFEST_VERSION:
            db.execute("UPDATE control SET pause_requested=0 WHERE EXISTS(SELECT 1 FROM batch WHERE status IN ('paused','interrupted'))")
        cursor = db.execute("UPDATE batch SET status='running', started_at=COALESCE(started_at,?), ended_at=NULL, error=NULL WHERE status IN ('pending','paused','interrupted')", (now(),))
        if cursor.rowcount != 1:
            raise ValueError('Only a new pending batch may be started; resume is not implemented')


def start_run(directory, ordinal, run):
    with connect(directory) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] == MANIFEST_VERSION:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT pause_requested FROM control WHERE id=1').fetchone()[0]:
                db.execute("UPDATE batch SET status='paused' WHERE status='running'")
                return False
            cursor = db.execute("UPDATE runs SET status='running',started_at=?,ended_at=NULL,output=NULL,error=NULL WHERE ordinal=? AND status IN ('pending','interrupted') AND configuration=?",
                                (now(), str(ordinal), json.dumps(run.to_dict())))
            if cursor.rowcount != 1:
                raise ValueError('Run is not pending or configuration differs')
            return True
        else:
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
        version = db.execute('PRAGMA user_version').fetchone()[0]
        batch['manifest_version'] = version or 1
        batch['pause_requested'] = bool(db.execute('SELECT pause_requested FROM control WHERE id=1').fetchone()[0]) if version == 2 else False
    batch['total'] = int(batch['total'])
    batch['counts'] = {state: counts.get(state, 0) for state in ('running','succeeded','failed','interrupted')}
    batch['counts']['pending'] = batch['total'] - sum(value for state, value in counts.items() if state != 'pending')
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
    version = snapshot.get('manifest_version', 1)
    if type(version) is not int or version not in (1, MANIFEST_VERSION):
        raise ValueError('Unsupported manifest version')
    if version == 1 and count_runs(plan) != total:
        raise ValueError('Declared total does not match the saved configuration')

    uri = (directory / 'manifest.sqlite3').as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        stored_version = db.execute('PRAGMA user_version').fetchone()[0]
        if stored_version != (0 if version == 1 else MANIFEST_VERSION):
            raise ValueError('Manifest version differs between JSON and SQLite')
        batches = [dict(row) for row in db.execute('SELECT id,total,status,created_at,started_at,ended_at,error FROM batch')]
        runs = [dict(row) for row in db.execute('SELECT ordinal,run_id,status,configuration,started_at,ended_at,output,error FROM runs')]
    if len(batches) != 1 or batches[0]['id'] != identifier:
        raise ValueError('Batch identifier mismatch between JSON and manifest')
    batch = batches[0]
    if batch['created_at'] != snapshot['created_at']:
        raise ValueError('Creation timestamp differs between JSON and manifest')
    if positive_decimal(batch['total']) != total:
        raise ValueError('Declared totals disagree between JSON and manifest')
    batch['manifest_version'] = version
    if version == MANIFEST_VERSION:
        from .experiment_batch import validate_run_configuration
        if len(runs) != total:
            raise ValueError('Incomplete batch: persisted queue')
        runs.sort(key=lambda row: positive_decimal(row['ordinal']))
        for ordinal, row in enumerate(runs, 1):
            if row['ordinal'] != str(ordinal) or row['run_id'] != f'{identifier}-{ordinal}':
                raise ValueError('Inconsistent run ordinal or run_id')
            try:
                validate_run_configuration(json.loads(row['configuration']), configuration)
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f'Run {ordinal}: {error}') from error
            if row['status'] not in ('pending','running','succeeded','failed','interrupted'):
                raise ValueError('Invalid run status')
            if row['status'] == 'pending' and any(row[k] is not None for k in ('started_at','ended_at','output','error')):
                raise ValueError('Inconsistent pending run status')
        if batch['status'] == 'pending' and (any(r['status'] != 'pending' for r in runs)
                or any(batch[k] is not None for k in ('started_at','ended_at','error'))):
            raise ValueError('Inconsistent pending batch status')
    return plan, batch, runs


def request_pause(directory, *, timeout=0.05):
    """Commit a cooperative request; never signal the solver."""
    with connect(directory, timeout=timeout) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] != MANIFEST_VERSION:
            raise ValueError('Legacy batch does not support pause or resume')
        cursor = db.execute("UPDATE control SET pause_requested=1 WHERE id=1 AND EXISTS(SELECT 1 FROM batch WHERE status IN ('pending','running'))")
        if cursor.rowcount != 1:
            raise ValueError('Batch is not running or starting')
