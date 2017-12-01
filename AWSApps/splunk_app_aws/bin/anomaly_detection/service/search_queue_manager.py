__author__ = 'pezhang'

import service_const
import time
import utils.app_util as app_util
import uuid

logger = app_util.get_logger()


class SearchQueueManager(object):
    """
        Search queue manager, be responsible for running anomaly search
    """

    def __init__(self, service, window_size=service_const.DEFAULT_WINDOW_SIZE, sleep_time=service_const.SLEEP_TIME):
        """
            :param service: used to initialize jobs handler
            :param window_size: integer, indicate the number of concurrent search jobs
            :param sleep_time: integer, indicate the seconds between successive check job done function
        """
        self.window_size = window_size
        self.sleep_time = sleep_time
        self.jobs = service.jobs
        self.wait_queues = []
        self.running_searches = {}

    def run_searches(self, searches):
        self.wait_queues = searches
        self.total_count = len(searches)
        self.transcation_id = str(uuid.uuid1())
        self.finished_count = 0
        for i in xrange(min(self.window_size, len(self.wait_queues))):
            self._start_next_search()
        self._run_and_check()

    def _start_next_search(self):
        if len(self.running_searches) >= self.window_size or len(self.wait_queues) <= 0:
            return

        search = self.wait_queues.pop(0)
        search_kwargs = search.get_earliest_latest()
        search_str = search.get_search() if search.get_search().lstrip()[0] == '|' else 'search ' + search.get_search()
        job = self.jobs.create(search_str, **search_kwargs)
        self.running_searches[job.sid] = {'job':job, 'id': search.get_id()}

    def _on_search_done(self, job):
        del self.running_searches[job.sid]
        self._start_next_search()
        if len(self.running_searches) == 0:
            return False
        return True

    def _run_and_check(self):
        while len(self.running_searches) > 0:
            for key, job_wrap in self.running_searches.items():
                is_job_done = job_wrap['job'].is_done()
                if is_job_done:
                    self.finished_count += 1
                    logger.info('transcation_id=%s, total_count=%d, finished_count=%d, done_job_stanza=%s' % (self.transcation_id, self.total_count, self.finished_count, job_wrap['id']))
                    self._on_search_done(job_wrap['job'])
            # because search will run for a while, use sleep to avoid continually requesting search status
            time.sleep(self.sleep_time)
