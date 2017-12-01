import os
from splunksdc import log as logging


class FSLock(object):
    @classmethod
    def _create_runtime(cls):
        if os.name == 'nt':
            import msvcrt   # pylint: disable=import-error

            def lock(fd):
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1024)

            def unlock(fd):
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1024)

            return lock, unlock
        else:
            import fcntl

            def lock(fd):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            def unlock(fd):
                fcntl.flock(fd, fcntl.LOCK_UN)

        return lock, unlock

    @classmethod
    def open(cls, path):
        lock, unlock = cls._create_runtime()
        flag = os.O_RDWR | os.O_CREAT | os.O_TRUNC
        fd = os.open(path, flag)
        return cls(fd, lock, unlock)

    def __init__(self, fd, lock, unlock):
        self._fd = fd
        self._lock = lock
        self._unlock = unlock

    def acquire(self):
        self._lock(self._fd)

    def release(self):
        self._unlock(self._fd)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LogExceptions(object):
    def __init__(self, logger, message, epilogue=None, types=Exception):
        self._logger = logger
        self._message = message
        self._epilogue = epilogue
        self._types = types

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except self._types as e:
                self._logger.exception(self._message)
                if self._epilogue:
                    return self._epilogue(e)
                raise e
        return wrapper


class LogWith(object):
    def __init__(self, **kwargs):
        self._pairs = kwargs.items()

    def __call__(self, func):
        pairs = self._pairs

        def wrapper(*args, **kwargs):
            ctx = dict()
            for key, value in pairs:
                if isinstance(value, property):
                    value = value.fget(args[0])
                ctx[key] = value
            with logging.LogContext(**ctx):
                return func(*args, **kwargs)
        return wrapper

