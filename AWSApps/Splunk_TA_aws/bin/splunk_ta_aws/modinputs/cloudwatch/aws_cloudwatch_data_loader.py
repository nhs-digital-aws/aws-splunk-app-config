import threading
import time
import random

import aws_cloudwatch_consts as acc
import splunksdc.log as logging
import aws_cloudwatch_checkpointer as ackpt
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import boto3


logger = logging.get_module_logger()


class CloudWatchClient(object):
    def __init__(self, config):
        self._server_uri = config[tac.server_uri]
        self._session_key = config[tac.session_key]
        self._aws_account = config[tac.aws_account]
        self._aws_iam_role = config[tac.aws_iam_role]
        self._region_name = config['region']
        self._credentials = self._load_credentials()
        self._client = self._create_boto3_client(self._credentials)

    def _load_credentials(self):
        credentials = tacommon.load_credentials_from_cache(
            self._server_uri,
            self._session_key,
            self._aws_account,
            self._aws_iam_role
        )
        return credentials

    def _create_boto3_client(self, credentials):
        self._client = boto3.client(
            'cloudwatch',
            region_name=self._region_name,
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            aws_session_token=credentials.aws_session_token
        )
        return self._client

    def require_boto3_client(self):
        if self._credentials.need_retire():
            credentials = self._load_credentials()
            self._client = self._create_boto3_client(credentials)
            self._credentials = credentials
        return self._client

    def get_account_id(self):
        return self._credentials.account_id


class CloudWatchDataLoader(object):

    def __init__(self, config):
        """
        :config: a list of dict object
        {
        "polling_interval": 60,
        "sourcetype": yyy,
        "index": zzz,
        "region": xxx,
        "key_id": aws key id,
        "secret_key": aws secret key
        "period": 60,
        "metric_namespace": namespace,
        "statistics": statistics
        "metric_configs": [
            {
                "Dimensions": [{"Value": "i-8b9eaa2f", "Name": "InstanceId"}],
                "MetricName": metric_name,
            },
        ],
        }
        """

        tacommon.set_proxy_env(config)
        self._config = config
        self._stopped = False
        self._lock = threading.Lock()
        self._ckpt = ackpt.CloudWatchCheckpointer(config)
        self._source = "{}:{}".format(
            config[tac.region], config[acc.metric_namespace])
        self._max_api_saver_count = \
            self._config[acc.max_api_saver_time] / self._config[acc.period]

        self._client = CloudWatchClient(config)

        self._supplemental_data = {
            acc.period: config[acc.period],
            tac.account_id: self._client.get_account_id(),
        }

    def __call__(self):
        with logging.LogContext(datainput=self._config[tac.datainput]):
            self.index_data()

    def index_data(self):
        start = time.time()
        with logging.LogContext(start_time=start):
            msg = "collecting cloudwatch namespace={}, metric_name={} datainput={}, end_time={}".format(
                self._config[acc.metric_namespace],
                self._config[acc.metric_configs][0]["MetricName"],
                self._config[tac.datainput],
                self._ckpt.max_end_time())

            if self._lock.locked():
                logger.debug(
                    "Last round of %s is not done yet", msg)
                return

            logger.info("Start %s", msg)
            with self._lock:
                try:
                    self._do_index_data()
                except Exception:
                    logger.exception("Failed of %s.", msg)
            logger.info("End of %s, one_batch_cost=%s", msg, time.time() - start)

    def _do_index_data(self):
        records = []
        for dimension in self._config[acc.metric_configs]:
            if self._stopped:
                return

            client = self._client.require_boto3_client()

            empty_poll = self._ckpt.get_empty_poll(dimension)
            if 2 <= empty_poll <= self._max_api_saver_count:
                self._ckpt.increase_empty_poll(dimension)
                logger.debug(
                    "Skip namespace=%s, dimension=%s, metric_name=%s, "
                    "datainput=%s to save API",
                    self._config[acc.metric_namespace],
                    dimension["Dimensions"], dimension["MetricName"],
                    self._config[tac.datainput])
                continue

            start, end = self._ckpt.get_time_range(dimension)
            datapoints = self._do_one_dimension(client, dimension, start, end)
            if datapoints:
                logger.debug("Successfully get statistics.",
                             dimension=dimension,
                             datainput=self._config[tac.datainput],
                             start=start,
                             end=end)
                self._ckpt.reset_empty_poll(dimension)
                self._ckpt.set_start_time(dimension, end)
                records.append([dimension, datapoints])
            else:
                logger.debug("Failed to get statistics.",
                             dimension=dimension,
                             datainput=self._config[tac.datainput],
                             start=start,
                             end=end)
                if empty_poll > self._max_api_saver_count:
                    self._ckpt.reset_empty_poll(dimension)
                self._ckpt.increase_empty_poll(dimension)

        if records:
            self._index_data(records)

    def _handle_too_many_datapoints(self, e, dimension):
        if (e.message and
                "InvalidParameterCombination" in e.message and
                "reduce the datapoints" in e.message):
            self._ckpt.progress_start_time(dimension, 1000)
            logger.info(
                "Handle too many datainputs for namespace=%s, dimension=%s,"
                "metric_name=%s, datainput=%s. New start_time=%s",
                self._config[acc.metric_namespace],
                dimension["Dimensions"],
                dimension["MetricName"],
                self._config[tac.datainput],
                self._ckpt.get_start_time(dimension))
            return True
        return False

    def _do_one_dimension(self, client, dimension, start_time, end_time):
        if start_time == end_time:
            return None

        # perf_start = time.time()
        logger.debug(
            "Collect dimensions=%s, start_time=%s, end_time=%s for datainput=%s",
            dimension, start_time, end_time, self._config[tac.datainput])

        for i in xrange(4):
            try:
                response = client.get_metric_statistics(
                    Namespace=self._config[acc.metric_namespace],
                    MetricName=dimension["MetricName"],
                    Dimensions=dimension["Dimensions"],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=self._config[acc.period],
                    Statistics=self._config[acc.statistics])
            except Exception as ex:
                if "Rate exceeded" in ex.message:
                    tacommon.sleep_until(
                        random.randint(20, 60), self.stopped)
                logger.exception(
                    "Failed to get metrics for namespace=%s, dimension=%s,"
                    "metric_name=%s, datainput=%s, start_time=%s, "
                    "end_time=%s.",
                    self._config[acc.metric_namespace],
                    dimension["Dimensions"],
                    dimension["MetricName"],
                    self._config[tac.datainput],
                    start_time, end_time)
                self._handle_too_many_datapoints(ex, dimension)
                tacommon.sleep_until(2 ** (i + 1), self.stopped)
            else:
                break
        else:
            return None

        if not tacommon.is_http_ok(response):
            logger.error(
                "Failed to get metrics for namespace=%s, dimension=%s, "
                "metric_name=%s, errorcode=%s.",
                self._config[acc.metric_namespace],
                dimension["Dimensions"],
                dimension["MetricName"],
                tacommon.http_code(response))
            return None

        # logger.debug("one_dimension_cost=%s", time.time() - perf_start)
        return response.get("Datapoints")

    @staticmethod
    def _build_dimension_str(dimension):
        return ",".join(
            ["{Name}=[{Value}]".format(**d)
             for d in sorted(dimension["Dimensions"])])

    def _index_data(self, records):
        writer = self._config[tac.event_writer]
        sourcetype = self._config.get(tac.sourcetype, "aws:cloudwatch")
        events = []
        for dimension, datapoints in records:
            for datapoint in datapoints:
                datapoint.update(self._supplemental_data)
                datapoint[acc.metric_dimensions] = self._build_dimension_str(
                    dimension)
                datapoint[acc.metric_name] = dimension["MetricName"]
                evt_time = tacommon.total_seconds(datapoint["Timestamp"])
                del datapoint["Timestamp"]
                event = writer.create_event(
                    index=self._config.get(tac.index, "default"),
                    host=self._config.get(tac.host, ""),
                    source=self._source,
                    sourcetype=sourcetype,
                    time=evt_time,
                    unbroken=False,
                    done=False,
                    events=datapoint)
                events.append(event)
        writer.write_events(events, retry=10)

    def get_interval(self):
        return self._config.get(tac.polling_interval, 60)

    def stop(self):
        self._stopped = True
        logger.info("CloudWatchDataLoader is going to exit")

    def stopped(self):
        return self._stopped or self._config[tac.data_loader_mgr].stopped()

    def get_props(self):
        return self._config
