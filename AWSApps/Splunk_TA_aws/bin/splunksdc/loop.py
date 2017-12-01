"""
The loop object responses for firing events and watching signals.
Currently, only watching signals is implemented. The name may change in future.
"""
import os
import signal
import multiprocessing
from splunksdc import log as logging


logger = logging.get_module_logger()


class LoopFactory(object):
    @classmethod
    def create(cls):
        loop_type = BasicLoop
        if os.name == 'posix':
            loop_type = PosixLoop
        loop = loop_type()
        loop.setup()
        return loop


class BasicLoop(object):
    def __init__(self):
        self._aborted = multiprocessing.Event()
        self._stopped = False

    def setup(self):
        signal.signal(signal.SIGINT, self.abort)
        signal.signal(signal.SIGTERM, self.abort)

    def is_aborted(self):
        if not self._stopped and self._aborted.is_set():
            self._stopped = True
            logger.info('Loop has been aborted.')
        return self._stopped

    def abort(self, *args, **kwargs):
        self._aborted.set()


class PosixLoop(BasicLoop):
    def __init__(self):
        super(PosixLoop, self).__init__()

    def setup(self):
        super(PosixLoop, self).setup()
        signal.signal(signal.SIGHUP, self.abort)
        signal.siginterrupt(signal.SIGINT, False)
        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGHUP, False)

    def is_aborted(self):
        super(PosixLoop, self).is_aborted()
        if not self._stopped and self._is_orphan():
            self._stopped = True
            logger.info('Parent process has been terminated.')
        return self._stopped

    @staticmethod
    def _is_orphan():
        return os.getppid() == 1
