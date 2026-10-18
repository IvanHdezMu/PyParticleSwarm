"""Process lifecycle for the desktop runner. No Tk calls or solver changes."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from ..infrastructure.experiment_options import ROOT
from .batch_store import batch_status, mark_interrupted


class BatchProcess:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.interrupt_started = None
        options = {'start_new_session': True} if os.name == 'posix' else {
            'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        with (self.directory / 'execution.log').open('w', encoding='utf-8') as stream:
            self.process = subprocess.Popen(
                [sys.executable, '-m', 'tsp_pso.experiments.batch_executor', str(self.directory)],
                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, **options)

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

    def poll(self):
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
            state = batch_status(self.directory)
            if state['status'] in ('pending', 'running'):
                mark_interrupted(self.directory, f'Execution process exited ({code}) without a completion record; see execution.log')
        return code
