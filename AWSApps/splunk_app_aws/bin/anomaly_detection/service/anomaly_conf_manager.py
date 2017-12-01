__author__ = 'pezhang'

import anomaly_detection.anomaly_detection_const as const
from datetime import datetime
from anomaly_job import AnomalyJob
import heapq
import utils.app_util as app_util

logger = app_util.get_logger()


class DefaultClock(object):
    """
        Use built-in datetime to get current time
    """

    def now(self):
        return datetime.now()


class AnomalyConfManager(object):
    """
        Configuration file manager. be responsible for reading conf files, getting current hour's task
        and writing conf file with stanza name and correp
    """

    def __init__(self, service, conf_name=const.CONF_NAME, clock=None):
        """
            :param service: used to initialize configuration file handler
            :param conf_name: the name of conf file which stored job settings
            :param clock: tools to get current time, mainly used for UT injection
        """
        self.conf = service.confs[conf_name]
        self._clock = DefaultClock() if clock is None else clock

    def get_jobs(self):
        """
            Reading conf files, getting current hour's task in priority order
        """
        query_string = self._get_query_string()
        anomaly_configs = self.conf.list(search=query_string)
        jobs = []
        for config in anomaly_configs:
            job = None

            try:
                job = AnomalyJob(config.name, config.content())
            except ValueError:
                logger.error('Stanza %s in anomalyconfigs.conf\' attributes are invalid.' % config.name)
            except AttributeError:
                logger.info('Stanza %s in anomalyconfigs.conf is disabled.' % config.name)

            if job is not None:
                jobs.append(job)
        return self._heapify(jobs)

    def _heapify(self, jobs):
        """
            Heapify a list (max-heap), job with highest priority will be searched first
        """
        max_heap = []
        for job in jobs:
            heapq.heappush(max_heap, (-job.get_priority(), job))
        results = []
        while len(max_heap) != 0:
            results.append(heapq.heappop(max_heap)[1])
        return results


    def _get_query_string(self):
        """
            Query string to get current hour's task
            If current hour is 0 o'clock, then it will run hourly job and daily job
            To reduce the burden of 0 o'clock, weekly job is moved to 1 o'click of each monday and
            monthly job is moved to 2 o'clock of 1st of each month
        """
        now = self._clock.now()
        hour = now.hour
        weekday = now.weekday()
        monthday = now.day
        search = 'job_schedule=Hourly'
        if hour == 0:
            search += ' OR job_schedule=Daily'
        elif weekday == 0 and hour == 1:
            search += ' OR job_schedule=Weekly'
        elif monthday == 1 and hour == 2:
            search += ' OR job_schedule=Monthly'
        return search


    def create_stanza(self, stanza_name, stanza_obj):
        """
            Writing to conf file with given stanza name and corresponding content
            :param stanza_name: given stanza name
            :param stanza_obj: given stanza attributes
        """
        self.conf.create(name=stanza_name, **stanza_obj)
