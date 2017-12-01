import time
import random
import traceback

import boto.logs
from boto.exception import JSONResponseError

import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunktalib.common.util as scutil
from splunksdc import logging

import aws_cloudwatch_logs_consts as aclc
import aws_cloudwatch_logs_checkpointer as checkpointer


logger = logging.get_module_logger()


def safe_get_log_events(cwlogs_conn, group_name, stream_name,
                        start_time=None, end_time=None, next_token=None,
                        limit=None, start_from_head=True):
    sleep_range = 1
    while True:
        try:
            buf = cwlogs_conn.get_log_events(
                group_name, stream_name,
                start_time=start_time, end_time=end_time,
                next_token=next_token, limit=limit,
                start_from_head=start_from_head)
            return buf
        except JSONResponseError as e:
            if getattr(e, "error_code") == "ThrottlingException":
                logger.debug("ThrottlingException received. Sleep a random "
                             "time between 0 and %s seconds", sleep_range)
                time.sleep(random.uniform(0, sleep_range))
                sleep_range *= 2
            else:
                raise


def get_cloudwatch_log_events(cwlogs_conn, group_name, stream_name, start_time,
                              end_time):
    events = []
    buf = safe_get_log_events(cwlogs_conn, group_name, stream_name,
                              start_time=start_time, end_time=end_time)
    while "events" in buf and buf["events"]:
        events.extend(buf["events"])
        buf = safe_get_log_events(cwlogs_conn, group_name, stream_name,
                                  start_time=start_time, end_time=end_time,
                                  next_token=buf["nextBackwardToken"])

    return events


def describe_cloudwatch_log_streams(cwlogs_conn, group_name):
    buf = {"nextToken": None}
    streams = []

    while "nextToken" in buf:
        try:
            buf = cwlogs_conn.describe_log_streams(
                group_name, next_token=buf["nextToken"])
            streams.extend(buf["logStreams"])
        except JSONResponseError as e:
            if getattr(e, "error_code") == "ThrottlingException":
                stime = random.uniform(2, 6)
                time.sleep(stime)
                logger.error(
                    "Failure in describing cloudwatch logs streams due to "
                    "throttling exception for log_group=%s, "
                    "sleep=%s, reason=%s",
                    group_name, stime, traceback.format_exc())
            else:
                raise

    return streams


class CloudWatchLogsDataLoader(object):

    _evt_fmt = ("<stream><event>"
                "<time>{time}</time>"
                "<source>{source}</source>"
                "<sourcetype>{sourcetype}</sourcetype>"
                "<index>{index}</index>"
                "<data>{data}</data>"
                "</event></stream>")

    def __init__(self, task_config):
        """
        :task_config: dict object
        {
        "interval": 30,
        "source": xxx,
        "sourcetype": yyy,
        "index": zzz,
        "checkpoint_dir": aaa,
        "log_group_name": xxx,
        }
        """

        self._task_config = task_config
        self._stopped = False

    def __call__(self):
        self.index_data()

    def index_data(self):
        task = self._task_config
        if task[aclc.lock].locked():
            logger.info("Previous job of the same task still running. "
                        "Exit current job. region=%s, log_group=%s",
                        task[tac.region], task[aclc.log_group_name])
            return

        logger.info("Start collecting cloudwatch logs for region=%s, "
                    "log_group=%s", task[tac.region],
                    task[aclc.log_group_name])
        try:
            self._do_index_data()
        except Exception:
            logger.error("Failed to collect cloudwatch logs for region=%s, "
                         "log_group=%s, error=%s", task[tac.region],
                         task[aclc.log_group_name], traceback.format_exc())
        logger.info("End of collecting cloudwatch logs for region=%s "
                    "log_group=%s", task[tac.region],
                    task[aclc.log_group_name])

    def _do_index_data(self):
        conn = tacommon.connect_service_to_region(
            boto.logs.connect_to_region, self._task_config)

        with self._task_config[aclc.lock]:
            while not self._stopped:
                done = self._collect_and_index(conn)
                if done:
                    break

    def _collect_and_index(self, conn):
        task = self._task_config
        logger.info("Start to describe streams. region=%s, log_group=%s",
                    task["region"], task["log_group_name"])
        try:
            streams = describe_cloudwatch_log_streams(
                conn, task["log_group_name"])
        except Exception:
            logger.error(
                "Failure in describing cloudwatch logs streams for "
                "log_group=%s, error=%s", task["log_group_name"],
                traceback.format_exc())
            return True

        logger.info("Got %s log streams for region=%s, log_group=%s",
                    len(streams), task["region"], task["log_group_name"])

        done = self._get_log_events_for_streams(streams, conn)
        if done:
            logger.info("End of describing streams. region=%s, log_group=%s",
                        task["region"], task["log_group_name"])
            return True
        else:
            logger.info("Continue collecting history data for region=%s, "
                        "log_group=%s", task["region"], task["log_group_name"])
            return False

    @staticmethod
    def _ignore_stream(stream, task, last_event_time):
        if not task[aclc.stream_matcher].match(stream["logStreamName"]):
            logger.debug("Ignore region=%s, log_group=%s, stream_name=%s, "
                         "stream_matcher=%s", task[tac.region],
                         task[aclc.log_group_name], stream["logStreamName"],
                         task[aclc.stream_matcher].pattern)
            return True

        for required in ("firstEventTimestamp", "lastEventTimestamp"):
            if required not in stream:
                return True

        if stream["lastEventTimestamp"] <= last_event_time:
            logger.info("Ignore region=%s, log_group=%s since it has not "
                        "events since %s", task[tac.region],
                        task[aclc.log_group_name], int(last_event_time))
            return True

        return False

    def _get_log_events_for_streams(self, streams, conn):
        """
        :return: True when all of the streams having not more events,
                 False otherwise
        """

        task = self._task_config
        time_win = task[tac.interval] * 1000 * 2
        ignored_streams = 0

        for stream in streams:
            logger.debug("Start process log_group=%s log_stream=%s",
                         task[aclc.log_group_name], stream["logStreamName"])
            if self._stopped:
                return True

            ckpt = checkpointer.CloudWatchLogsCheckpointer(task, stream)
            s_time = ckpt.start_time()

            if self._ignore_stream(stream, task, s_time):
                ignored_streams += 1
                continue

            e_time = s_time + time_win
            if e_time >= stream["lastEventTimestamp"]:
                e_time = stream["lastEventTimestamp"] + 1

            try:
                results = get_cloudwatch_log_events(
                    conn, task[aclc.log_group_name], stream["logStreamName"],
                    s_time, e_time)
            except Exception:
                logger.error(
                    "Failure in getting cloudwatch logs events: %s",
                    traceback.format_exc())
                continue

            self._index_events(results, stream["logStreamName"])
            ckpt.save(e_time)
        return ignored_streams == len(streams)

    def _index_events(self, results, stream_name):
        evt_fmt = self._evt_fmt
        task = self._task_config
        region = task[tac.region]
        log_group_name = task[aclc.log_group_name]
        events = []
        for result in results:
            source = "{region}:{log_group}:{stream}".format(
                region=region, log_group=log_group_name, stream=stream_name)
            event = evt_fmt.format(
                source=source, sourcetype=task[tac.sourcetype],
                index=task[tac.index],
                data=scutil.escape_cdata(result["message"]),
                time=result["timestamp"] / 1000.0)
            events.append(event)
        task["writer"].write_events("".join(events))

    def get_interval(self):
        return self._task_config[tac.interval]

    def stop(self):
        self._stopped = True

    def get_props(self):
        return self._task_config
