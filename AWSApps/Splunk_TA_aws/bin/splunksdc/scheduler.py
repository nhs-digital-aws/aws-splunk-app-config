import time
from collections import Iterable
from sortedcontainers import SortedSet
from splunksdc import log as logging


logger = logging.get_module_logger()


class TaskEntry(object):
    def __init__(self, params, due, interval):
        self._params = params
        self._due = due
        self._interval = interval

    @property
    def params(self):
        return self._params

    @property
    def interval(self):
        return self._interval

    @property
    def due(self):
        return self._due

    def update_due_time(self):
        self._due += self._interval


class TaskScheduler(object):
    def __init__(self, executor, now=time.time):
        self._tasks = dict()
        self._max_concurrent = 4
        self._running_tasks = dict()
        self._scheduled_tasks = SortedSet(key=self._compare_by_due)
        self._executor = executor
        self._now = now

    def _compare_by_due(self, task_id):
        return self._tasks[task_id].due

    def idle(self):
        if len(self._tasks) == 0:
            return True
        if not self._running_tasks and not self._scheduled_tasks:
            return True
        return False

    def add_task(self, task_id, params, interval):
        """
        :param task_id: The unique id of task. 
        :param params: Any picklable parameters.
        :param interval: interval should >=0, 0 means one time task.
        :return: 
        """
        if task_id in self._tasks:
            raise ValueError('Task {} already exists.'.format(task_id))

        if interval < 0:
            raise ValueError('Interval should >= 0.')

        now = self._now()
        self._tasks[task_id] = TaskEntry(params, now, interval)
        self._scheduled_tasks.add(task_id)
        return True

    def set_max_number_of_worker(self, value):
        self._max_concurrent = value

    def _schedule(self):
        executor = self._executor
        now = self._now()
        for task_id in self._find_finished_task():
            del self._running_tasks[task_id]
            entry = self._tasks[task_id]
            if entry.interval:
                self._scheduled_tasks.add(task_id)

        quota = self._get_free_running_slot()
        for _ in range(quota):
            task_id = self._find_nearest_task()
            if not task_id:
                break
            entry = self._tasks[task_id]
            if entry.due > now:
                break
            self._scheduled_tasks.remove(task_id)
            entry.update_due_time()
            logger.debug('Task will be perform.', task_id=task_id)
            worker = executor.create(task_id, entry.params)
            self._running_tasks[task_id] = worker

        wait_seconds = 0.1
        task_id = self._find_nearest_task()
        if task_id:
            entry = self._tasks[task_id]
            if entry.due > now:
                wait_seconds = float(entry.due - now)
                wait_seconds = max(wait_seconds, 0.1)
                wait_seconds = min(wait_seconds, 1)
        return wait_seconds

    def _find_nearest_task(self):
        if len(self._scheduled_tasks):
            return self._scheduled_tasks[0]
        return ''

    def _find_finished_task(self):
        executor = self._executor
        tasks = set()
        for task_id, worker in self._running_tasks.items():
            if worker.poll():
                tasks.add(task_id)
                executor.release(worker)
                logger.debug('Task has been finished.', task_id=task_id)
        return tasks

    def run(self, callbacks):
        while not self.idle():
            timeout = self._schedule()
            if self._poll(callbacks):
                break
            time.sleep(timeout)

    def _get_free_running_slot(self):
        count = self._max_concurrent - len(self._running_tasks)
        return max(count, 0)

    @staticmethod
    def _poll(callbacks):
        if not isinstance(callbacks, Iterable):
            return False
        return any([func() for func in callbacks])


