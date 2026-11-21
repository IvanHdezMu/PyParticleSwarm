"""Process lifecycle for the desktop runner. No Tk calls or solver changes."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from ..infrastructure.experiment_options import ROOT
from .batch_store import batch_status, mark_interrupted, request_pause


class BatchProcess:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.interrupt_started = None
        options = {'start_new_session': True} if os.name == 'posix' else {
            'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        with (self.directory / 'execution.log').open('a', encoding='utf-8') as stream:
            self.process = subprocess.Popen(
                [sys.executable, '-m', 'tsp_pso.experiments.batch_executor', str(self.directory)],
                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, **options)

    def pause(self):
        request_pause(self.directory)

    def interrupt(self):
        if self.process.poll() is None and self.interrupt_started is None:
            self.interrupt_started = time.monotonic()
            try:
                if os.name == 'posix':
                    os.killpg(self.process.pid, signal.SIGINT)
                else:
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
            except ProcessLookupError:
                pass

    def poll(self, *, sqlite_timeout=10):
        if (self.interrupt_started is not None and self.process.poll() is None
                and time.monotonic() - self.interrupt_started > 8):
            if os.name == 'posix':
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                               capture_output=True, check=False)
        code = self.process.poll()
        if code is not None:
            state = batch_status(self.directory, timeout=sqlite_timeout)
            if state['status'] in ('pending', 'running'):
                message = f'Execution process exited ({code}) without a completion record; see execution.log'
                if (self.directory / 'manifest.sqlite3').exists():
                    with connect(self.directory, timeout=sqlite_timeout) as db:
                        modern = db.execute('PRAGMA user_version').fetchone()[0] == 2
                else:
                    modern = False
                if modern:
                    try:
                        with execution_lock(self.directory, claim=False):
                            mark_interrupted(self.directory, message, timeout=sqlite_timeout)
                    except ValueError:
                        # A surviving owner/group is authoritative, not this child's exit.
                        pass
                else:
                    mark_interrupted(self.directory, message, timeout=sqlite_timeout)
        return code


def _owner_alive(owner):
    """Conservative recovery: never restart beside a surviving process group."""
    if not owner:
        return False
    if sys.platform != 'linux':
        raise ValueError('Recovery of an existing owner requires Linux process-group verification')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if owner['boot'] != boot:
        return False
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
        except FileNotFoundError:
            continue
        # Zombie processes cannot write results. Include spawned/forkserver workers.
        if fields[0] != 'Z' and int(fields[2]) == owner['pgid']:
            if int(path.parent.name) != os.getpid():
                return True
    return False


from contextlib import contextmanager
import json
from .batch_store import connect


@contextmanager
def execution_lock(directory, *, claim=True):
    """OS exclusion for the coordinator lifetime, without a long SQL transaction."""
    directory = Path(directory)
    with (directory / '.execution.lock').open('a+b') as lock:
        if os.name == 'posix':
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('Batch already has an active coordinator') from error
        else:
            import msvcrt
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError('Batch already has an active coordinator') from error
        with connect(directory) as db:
            owner = db.execute('SELECT owner FROM control WHERE id=1').fetchone()[0]
            if owner and _owner_alive(json.loads(owner)):
                raise ValueError('Previous batch process group is still alive; recovery refused')
            owner = dict(pid=os.getpid(), pgid=os.getpgrp() if os.name == 'posix' else os.getpid(),
                         boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                         if sys.platform == 'linux' else None)
            if claim:
                db.execute('UPDATE control SET owner=? WHERE id=1', (json.dumps(owner),))
        try:
            yield
        finally:
            # Normal direct API calls may share the caller's process group. A
            # subprocess owns its own group; retain its evidence until it exits.
            if claim and owner['pid'] != owner['pgid']:
                with connect(directory) as db:
                    db.execute('UPDATE control SET owner=NULL WHERE id=1')
