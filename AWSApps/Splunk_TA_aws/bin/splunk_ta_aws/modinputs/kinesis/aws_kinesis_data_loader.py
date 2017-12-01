import traceback
import threading
import time
import json

import aws_kinesis_consts as akc
import splunksdc.log as logging

logger = logging.get_module_logger()


import splunktalib.common.util as scutil
import aws_kinesis_checkpointer as ackpt
import aws_kinesis_common as akcommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon


@scutil.catch_all(logger, reraise=True, default_result=[])
def handle_cloudwatchlogs_fmt_records(data, config, writer):
    index = config.get(tac.index, "default")
    host = config.get(tac.host, "")
    now = time.time() * 1000
    records = json.loads(data)

    events = []
    source = "{region}:{log_group}:{stream}".format(
        region=config[tac.region], log_group=records["logGroup"],
        stream=records["logStream"])

    for evt in records["logEvents"]:
        event = writer.create_event(
            index=index,
            host=host,
            source=source,
            sourcetype=config.get(tac.sourcetype),
            time=evt.get("timestamp", now) / 1000.0,
            unbroken=False,
            done=False,
            events=evt["message"])
        events.append(event)
    return events


class KinesisDataLoader(object):

    def __init__(self, config):
        """
        :config: dict object
        {
        "interval": 36000,
        "sourcetype": yyy,
        "index": zzz,
        "region": xxx,
        "key_id": aws key id,
        "secret_key": aws secret key
        "stream_name": stream name,
        "shard_id": shard_id,
        "init_stream_position": TRIM_HORIZON or LATEST
        }
        """

        self._config = config
        self._stopped = False
        self._lock = threading.Lock()
        self._ckpt = ackpt.AWSKinesisCheckpointer(config)
        self._source = "{stream_name}:{shard_id}".format(
            stream_name=self._config["stream_name"],
            shard_id=self._config["shard_id"])
        self._msg = ("from Kinesis stream={}, shard_id={}, "
                     "datainput={}").format(
                         self._config[akc.stream_name],
                         self._config[akc.shard_id],
                         self._config[tac.datainput])

    def __call__(self):
        self.index_data()

    def index_data(self):
        if self._lock.locked():
            return

        logger.info("Start collecting %s", self._msg)

        with self._lock:
            try:
                self._do_index_data()
            except Exception:
                logger.exception("Failed of collecting %s", self._msg)
        logger.info("End of collecting %s", self._msg)

    def _do_index_data(self):
        self._set_stream_position()
        self._client = akcommon.KinesisClient(self._config, logger)
        start, total_indexed = time.time(), 0
        for records in self._client.get_records():
            if not records:
                continue

            if self._stopped:
                return

            logger.debug("Got %d records %s", len(records), self._msg)
            total_indexed = self._index_data(records)
            if total_indexed >= 1000:
                logger.info("Collecting %s for 1000 takes=%s seconds",
                            self._msg, time.time() - start)
                start = time.time()
                total_indexed = 0

            self._ckpt.set_sequence_number(records[-1]["SequenceNumber"])

    def _handle_fmt_record(self, rec, events):
        rec_fmt = self._config.get(akc.record_format, "")
        sourcetype = self._config.get(tac.sourcetype, "aws:kinesis")
        if sourcetype == "aws:cloudwatchlogs:vpcflow" or rec_fmt == akc.cloudwatchlogs:
            try:
                events.extend(
                    handle_cloudwatchlogs_fmt_records(
                        rec["Data"], self._config,
                        self._config[tac.event_writer]))
            except Exception:
                return False
            else:
                return True
        else:
            return False

    def _index_data(self, records):
        indexed = 0
        events = []
        writer = self._config[tac.event_writer]

        for rec in records:
            if not rec["Data"]:
                continue
            indexed += 1
            handled = self._handle_fmt_record(rec, events)
            if not handled:
                evt_time = tacommon.total_seconds(
                    rec["ApproximateArrivalTimestamp"])

                data = scutil.try_convert_to_json(rec["Data"])
                event = writer.create_event(
                    index=self._config.get(tac.index, "default"),
                    host=self._config.get(tac.host, ""),
                    source=self._source,
                    sourcetype=self._config.get(tac.sourcetype, "aws:kinesis"),
                    time=evt_time,
                    unbroken=False,
                    done=False,
                    events=data)
                events.append(event)

        try:
            writer.write_events(events, retry=30)
        except Exception:
            logger.error(
                "Failed to index events %s, error=%s",
                self._msg, traceback.format_exc())
            raise
        logger.debug("Indexed %d records %s", len(events), self._msg)
        return indexed

    def get_interval(self):
        return self._config.get(tac.polling_interval, 10)

    def stop(self):
        self._stopped = True
        logger.info("KinesisDataLoader is going to exit")

    def stopped(self):
        return self._stopped or self._config[tac.data_loader_mgr].stopped()

    def get_props(self):
        return self._config

    def _set_stream_position(self):
        sequence_number = self._ckpt.sequence_number()
        if sequence_number:
            logger.info(
                "Pick up from sequence_number=%s for stream=%s, shard_id=%s, "
                "datainput=%s", sequence_number, self._config[akc.stream_name],
                self._config[akc.shard_id], self._config[tac.datainput])
            self._config[akc.sequence_number] = sequence_number
            self._config[akc.shard_iterator_type] = akcommon.KinesisClient.AFTER_SEQUENCE_NUMBER
        else:
            self._config[akc.shard_iterator_type] = self._config[akc.init_stream_position]
