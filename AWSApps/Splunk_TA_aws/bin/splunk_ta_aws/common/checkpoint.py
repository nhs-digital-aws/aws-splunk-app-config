"""
Thread safe checkpoint.
"""

import threading
from splunksdc.checkpoint import LocalKVStore


class LocalKVService(object):
    @classmethod
    def create(cls, filename):
        store = LocalKVStore.open_always(filename)
        server = cls(store)
        return server

    def __init__(self, store):
        self._lock = threading.Lock()
        self._store = store

    def set(self, key, value, flush=True):
        with self._lock:
            return self._store.set(key, value, flush=flush)

    def get(self, key):
        with self._lock:
            return self._store.get(key)

    def delete(self, key):
        with self._lock:
            return self._store.delete(key)

    def flush(self):
        with self._lock:
            return self._store.flush()

    def range(self, minimum=None, maximum=None, policy=(True, True), reverse=False):
        with self._lock:
            return [key for key in self._store.range(
                minimum=minimum,
                maximal=maximum,
                policy=policy,
                reverse=reverse
            )]

    def prefix(self, prefix, reverse=False):
        with self._lock:
            return [key for key in self._store.prefix(prefix, reverse)]

    def sweep(self):
        with self._lock:
            return self._store.sweep()

    def close(self, sweep=False):
        return self._store.close(sweep)

    def close_and_remove(self):
        return self._store.close_and_remove()
