"""Manage the process pool used to evaluate particles."""

from multiprocessing import Pool


class ParticleExecutor:
    def __enter__(self):
        self._context = Pool()
        self._pool = self._context.__enter__()
        return self

    def map(self, function, iterable):
        return self._pool.map(function, iterable)

    def __exit__(self, exc_type, exc_value, traceback):
        return self._context.__exit__(exc_type, exc_value, traceback)
