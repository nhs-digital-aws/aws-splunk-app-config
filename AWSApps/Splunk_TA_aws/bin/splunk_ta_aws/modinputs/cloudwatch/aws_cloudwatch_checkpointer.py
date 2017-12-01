from datetime import datetime
from datetime import timedelta
import os

import aws_cloudwatch_consts as acc
import splunksdc.log as logging
import splunk_ta_aws.common.ta_aws_consts as tac
import json


logger = logging.get_module_logger()


class CloudWatchCheckpointer(object):

    MAX_STAT_GRACE_PERIOD_SECS = int(os.environ.get(
        "MAX_STAT_GRACE_PERIOD_SECS", 240))
    MAX_QUERY_WINDOW_DELTA = timedelta(hours=48)

    def __init__(self, config):
        self._config = config
        self.period_minutes = self._config[acc.period] / 60
        self._ckpts = self._populate_ckpts()

    def _populate_ckpts(self):
        end_time = self.max_end_time()
        start_time = end_time - timedelta(seconds=self._config[acc.period])

        ckpts = {}
        for dimension in self._config[acc.metric_configs]:
            key = self._get_key(dimension)
            # [start_time, empty_poll]
            ckpts[key] = [start_time, 0]
        return ckpts

    @staticmethod
    def _get_key(dimension):
        return json.dumps(dimension)

    def get_time_range(self, dimension):
        key = self._get_key(dimension)
        start_time, _ = self._ckpts.get(key)
        end_time = start_time
        max_etime = self.max_end_time()
        while 1:
            end_time += timedelta(seconds=self._config[acc.period])
            if end_time > max_etime:
                end_time -= timedelta(seconds=self._config[acc.period])
                break

        # ensure the query window is under an hour to support the
        # maximum number of datapoints in a query.
        if end_time - start_time > self.MAX_QUERY_WINDOW_DELTA:
            logger.warn(
                "There are no metrics in more than %s seconds",
                self.MAX_QUERY_WINDOW_DELTA.total_seconds(),
                namespace=self._config[acc.metric_namespace],
                dimensions=dimension["Dimensions"],
                metric_name=dimension["MetricName"],
                datainput=self._config[tac.datainput])

            # revise start_time to progress start_time/end_time
            start_time += end_time - start_time - self.MAX_QUERY_WINDOW_DELTA
            self._ckpts[key][0] = start_time
            max_delta = int(self.MAX_QUERY_WINDOW_DELTA.total_seconds())
            end_time = start_time + timedelta(
                seconds=max_delta / self._config[acc.period] * self._config[acc.period])
        return start_time, end_time

    def get_start_time(self, dimension):
        return self._ckpts[self._get_key(dimension)][0]

    def progress_start_time(self, dimension, period_num=1):
        key = self._get_key(dimension)
        start_time, _ = self._ckpts.get(key)
        start_time += timedelta(seconds=self._config[acc.period] * period_num)
        end_time = self.max_end_time()
        if start_time > end_time:
            start_time = end_time - timedelta(seconds=self._config[acc.period])
        self._ckpts[key][0] = start_time

    def set_start_time(self, dimension, new_start):
        key = self._get_key(dimension)
        self._ckpts[key][0] = new_start

    def max_end_time(self):
        delta = timedelta(seconds=self.MAX_STAT_GRACE_PERIOD_SECS)
        end_time = datetime.utcnow() - delta
        end_time = datetime(
            end_time.year, end_time.month, end_time.day, end_time.hour,
            end_time.minute / self.period_minutes * self.period_minutes)
        return end_time

    def increase_empty_poll(self, dimension):
        key = self._get_key(dimension)
        self._ckpts[key][1] += 1

    def reset_empty_poll(self, dimension):
        key = self._get_key(dimension)
        self._ckpts[key][1] = 0

    def get_empty_poll(self, dimension):
        key = self._get_key(dimension)
        return self._ckpts[key][1]
