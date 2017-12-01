from collections import Iterable
import Queue
import threading
from splunksdc import log as logging
from splunksdc.utils import LogWith


_DEFAULT_MAX_NUMBER_OF_THREAD = 4


class BatchExecutorExit(object):
    def __init__(self, exhausted):
        self.exhausted = exhausted


class BatchExecutor(object):
    def __init__(self, **kwargs):
        self._number_of_worker = kwargs.pop('number_of_threads', _DEFAULT_MAX_NUMBER_OF_THREAD)
        self._completed_queue = Queue.Queue(self._number_of_worker)
        self._pending_queue = Queue.Queue()
        self._stopped = threading.Event()
        self._main_context = logging.ThreadLocalLoggingStack.top()

    def _spawn(self, delegate):
        workers = list()
        for _ in range(self._number_of_worker):
            resources = delegate.allocate()
            args = [delegate.do]
            if not isinstance(resources, Iterable):
                resources = [resources]
            args.extend(resources)
            worker = threading.Thread(
                target=self._worker_procedure,
                args=args,
            )
            worker.daemon = True
            workers.append(worker)
        for worker in workers:
            worker.start()
        return workers

    def run(self, delegate):
        self._stopped.clear()
        exhausted = False
        workers = self._spawn(delegate)

        for jobs in delegate.discover():
            if isinstance(jobs, BatchExecutorExit):
                exhausted = jobs.exhausted
                break

            number_of_pending = 0
            for job in jobs:
                self._pending_queue.put(job)
                number_of_pending += 1

            while number_of_pending > 0:
                if delegate.is_aborted():
                    break
                try:
                    job, result = self._completed_queue.get(timeout=3)
                    delegate.done(job, result)
                    number_of_pending -= 1
                except Queue.Empty:
                    pass

            if delegate.is_aborted():
                break

        self._stopped.set()

        for worker in workers:
            worker.join(10.0)

        return exhausted

    @property
    def main_context(self):
        return self._main_context

    @LogWith(prefix=main_context)
    def _worker_procedure(self, procedure, *args):
        while not self._stopped.is_set():
            try:
                job = self._pending_queue.get(timeout=3)
                result = procedure(job, *args)
                self._completed_queue.put((job, result))
            except Queue.Empty:
                pass
        return

