import re
import threading
import Queue
import os.path as op
import os
import json

# FIXME Legacy code started
import splunk_ta_aws.common.proxy_conf as tpc
# Legacy code done


import boto3
from splunksdc import logging
import aws_cloudwatch_consts as acc
from splunk_ta_aws import set_log_level
import splunk_ta_aws.common.aws_concurrent_data_loader as acdl
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunktalib.conf_manager.conf_manager as cm
import splunktalib.common.util as scutil
import splunktalib.file_monitor as fm
import splunktalib.rest as sr


logger = logging.get_module_logger()


def create_conf_monitor(callback):
    files = (AWSCloudWatchConf.app_file,
             AWSCloudWatchConf.task_file_w_path,
             AWSCloudWatchConf.passwords_file_w_path,
             AWSCloudWatchConf.conf_file_w_path)

    return fm.FileMonitor(callback, files)


class AWSCloudWatchConf(object):

    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    task_file = "inputs"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")
    conf_file = "aws_cloudwatch"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")
    log_info = "log_info"
    log_info_w_path = op.join(app_dir, "local", log_info + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws
        self.server_uri = self.metas[tac.server_uri]
        self.session_key = self.metas[tac.session_key]

    def get_tasks(self):
        if not self.stanza_configs:
            return None

        conf_mgr = cm.ConfManager(self.server_uri, self.session_key)

        settings = conf_mgr.all_stanzas_as_dicts(
            self.conf_file, do_reload=False)

        # set logging level for our logger
        set_log_level(settings[tac.log_stanza][tac.log_level])

        proxy_info = tpc.get_proxy_info(self.session_key)
        tasks, creds = {}, {}
        for stanza in self.stanza_configs:
            input_name = scutil.extract_datainput_name(stanza[tac.name])
            with logging.LogContext(datainput=input_name):
                stanza[tac.interval] = tacommon.get_interval(stanza, 60)
                stanza[tac.polling_interval] = stanza[tac.interval]
                stanza[acc.period] = int(stanza[acc.period])

                if stanza[acc.period] > 86400 or stanza[acc.period] < 60:
                    logger.error(
                        "Granularity(period) is not in range[60, 86400], ignore this input.",
                        Period=stanza[acc.period],
                        ErrorCode="ConfigurationError",
                        ErrorDetail="Invalid Granularity(period). It's out of range [60, 86400].")
                    continue

                if stanza[tac.polling_interval] % stanza[acc.period]:
                    logger.error(
                        "Polling interval is not multiple of period, ignore this input.",
                        Period=stanza[acc.period],
                        ErrorCode="ConfigurationError",
                        ErrorDetail="Polling interval should be a multiple of granularity(period).")
                    continue

                stanza[tac.datainput] = input_name
                stanza[tac.sourcetype] = stanza.get(
                    tac.sourcetype, "aws:cloudwatch")
                metric_names = stanza[acc.metric_names].strip()
                if metric_names != ".*":
                    metric_names = json.loads(metric_names)
                else:
                    metric_names = None
                stanza[acc.metric_names] = metric_names

                stanza[acc.metric_dimensions] = json.loads(
                    stanza[acc.metric_dimensions])
                stanza[acc.statistics] = json.loads(stanza[acc.statistics])

                stanza[tac.log_level] = settings[tac.log_stanza][tac.log_level]

                stanza[tac.aws_account] = stanza.get('aws_account')
                stanza[tac.aws_iam_role] = stanza.get('aws_iam_role')

                stanza.update(self.metas)
                stanza.update(proxy_info)
                stanza.update(settings[tac.global_settings])
                stanza[acc.max_api_saver_time] = \
                    int(stanza.get(acc.max_api_saver_time, 7200))

                region_tasks = {}
                tasks[stanza[tac.datainput]] = region_tasks
                for region in stanza[tac.aws_region].split(","):
                    region = region.strip()
                    if not region:
                        continue

                    task = {}
                    task.update(stanza)
                    task[tac.aws_region] = region
                    task[tac.region] = region
                    num, rtasks = self._expand_task(task)
                    if rtasks:
                        region_tasks[region] = rtasks
                    stanza[region] = num

                if not region_tasks:
                    logger.warning("No metric/dimension has been found.")

        all_tasks = []
        for region_tasks in tasks.itervalues():
            for rtasks in region_tasks.itervalues():
                all_tasks.extend(rtasks)
        tacommon.handle_hec(all_tasks, "aws_cloudwatch")

        return all_tasks

    @staticmethod
    def _get_batch_size(total_num):
        min_batch_size = 10
        min_batch = 10
        max_batch_env = int(os.environ.get("aws_cloudwatch_max_batch", "200"))
        max_batch = min(
            max_batch_env, 64 * acdl.AwsDataLoaderManager.cpu_for_workers())

        if total_num <= min_batch_size:
            return total_num

        if total_num <= min_batch * min_batch_size:
            return min_batch_size

        batch_size = min_batch_size
        while 1:
            if total_num / batch_size > max_batch:
                batch_size = int(batch_size * 1.5)
            else:
                break

        return int(batch_size)

    def _expand_task(self, task):
        metrics = get_metrics(task)
        if not metrics:
            return 0, []

        total = len(metrics)
        batch_size = self._get_batch_size(total)
        logger.info(
            "Discovered total=%s metrics and dimentions in namespace=%s, "
            "region=%s for datainput=%s, batchsize=%s",
            total, task[acc.metric_namespace], task[tac.region],
            task[tac.datainput], batch_size)

        batched_tasks = []
        for i in range(total / batch_size):
            batched_tasks.append(metrics[i * batch_size: (i + 1) * batch_size])

        # Last batch
        if total > batch_size and total % batch_size < batch_size / 4:
            # Avoid too small batch size
            begin = total / batch_size * batch_size
            last_small_batch = metrics[begin: total]
            batched_tasks[-1].extend(last_small_batch)
        else:
            last_pos = total / batch_size * batch_size
            batched_tasks.append(metrics[last_pos: total])

        expanded_tasks = []
        for batch in batched_tasks:
            if not batch:
                continue

            new_task = dict(task)
            new_task[acc.metric_configs] = batch
            new_task[tac.aws_service] = tac.cloudwatch
            expanded_tasks.append(new_task)
        return total, expanded_tasks


def match_dimension(metric, dimension_regex_filters):
    if not dimension_regex_filters:
        return True

    for matcher in dimension_regex_filters:
        if matcher.exact_match(metric["Dimensions"]):
            return True
    return False


def _do_filter_invalid_dimensions(
        describe_func, result_key, instance_key, id_key, metrics, tag):
    exists = set()
    params = {
        "DryRun": False
    }

    while 1:
        try:
            response = describe_func(**params)
        except Exception:
            # When we encountered any errors, just return what we have
            logger.exception("Failed to describe instances for %s.", tag)
            return metrics, []

        if not tacommon.is_http_ok(response):
            logger.error(
                "Failed to describe instances for %s, error=%s", tag, response)
            return metrics, []

        if not response.get(result_key):
            break

        for instance in response[result_key]:
            if instance_key:
                for dim in instance[instance_key]:
                    exists.add(dim[id_key])
            else:
                exists.add(instance[id_key])

        token = response.get("NextToken")
        if token is None:
            break
        else:
            params["NextToken"] = token

    new_metrics, removed = [], []

    def _should_keep(metric):
        for dimension in metric["Dimensions"]:
            if dimension["Name"] == id_key:
                return dimension["Value"] in exists
        # if dimension does not match, do not filter
        return True

    for m in metrics:
        if _should_keep(m):
            new_metrics.append(m)
        else:
            removed.append(m)

    if logger.isEnabledFor(logging.INFO):
        logger.info(
            "%s total=%d, valid=%d, filtered=%d",
            tag, len(metrics), len(new_metrics),
            len(metrics) - len(new_metrics))

        i, total = 0, len(removed)
        while 1:
            filtered_ids = ",".join(d["Value"] for m in removed[i: i + 100]
                                    for d in m["Dimensions"])
            if filtered_ids:
                logger.info("filtered_ids=%s", filtered_ids)

            if i >= total:
                break
            i += 100

    return new_metrics, removed


def filter_invalid_ec2_instances(client, metrics, tag):
    valid_metrics, removed = _do_filter_invalid_dimensions(
        client.describe_instances, "Reservations", "Instances",
        "InstanceId", metrics, tag)
    return valid_metrics


def filter_invalid_ebs(client, metrics, tag):
    valid_metrics, _ = _do_filter_invalid_dimensions(
        client.describe_volumes, "Volumes", "", "VolumeId", metrics, tag)
    return valid_metrics


def filter_invalid_dimensions(namespace, metrics, config):
    # For now we only care EC2/EBS
    filter_map = {
        "AWS/EC2": {"service": "ec2",
                    "func": filter_invalid_ec2_instances,
                    "filter_key": "InstanceId"},
        "AWS/EBS": {"service": "ec2",
                    "func": filter_invalid_ebs,
                    "filter_key": "VolumeId"},
    }

    def _should_not_filter():
        # if metric dimensions do not contain filter_key,
        # directly return to save api call
        for metric in metrics:
            for dimension in metric["Dimensions"]:
                if dimension["Name"] == filter_map[namespace]["filter_key"]:
                    return False
        return True

    if namespace not in filter_map:
        return metrics
    elif _should_not_filter():
        return metrics

    server_uri = config[tac.server_uri]
    session_key = config[tac.session_key]
    aws_account = config[tac.aws_account]
    aws_iam_role = config[tac.aws_iam_role]
    credentials = tacommon.load_credentials_from_cache(
        server_uri,
        session_key,
        aws_account,
        aws_iam_role
    )

    client = boto3.client(
        filter_map[namespace]["service"],
        region_name=config[tac.region],
        aws_access_key_id=credentials.aws_access_key_id,
        aws_secret_access_key=credentials.aws_secret_access_key,
        aws_session_token=credentials.aws_session_token
    )

    tag = config[tac.datainput] + ":" + config[tac.region] + ":" + namespace
    return filter_map[namespace]["func"](client, metrics, tag)


def list_metrics_by_metric_name(client, namespace,
                                metric_name, dimension_regex_filters):
    all_metrics = []
    filtered = False
    params = {
        "Namespace": namespace,
    }

    if metric_name:
        params["MetricName"] = metric_name

    num_of_metrics_fetched = 0
    while 1:
        response = client.list_metrics(**params)
        if not tacommon.is_http_ok(response):
            logger.error("Failed to list_metrics for %s, error=%s",
                         params, response)
            break

        for metric in response["Metrics"]:
            if not metric["Dimensions"]:
                continue
            num_of_metrics_fetched += 1
            if not match_dimension(metric, dimension_regex_filters):
                continue

            del metric["Namespace"]
            all_metrics.append(metric)
        token = response.get("NextToken")
        if token is None:
            break
        else:
            params["NextToken"] = token
    if num_of_metrics_fetched and not all_metrics:
        logger.warning("All dimensions of this metric were filtered out.",
                       metric_name=metric_name,
                       filtered_metrics_num=num_of_metrics_fetched,
                       ErrorCode="ConfigurationError")
        filtered = True
    return (all_metrics, filtered)


def list_metrics(config, dimension_regex_filters):
    """
    :return: a list of following dicts
    {
    "namespace": string,
    "dimensions": dict,
    "metric_name": string,
    }
    """
    logger.info("Start querying metrics for metric_names=%s, namespace=%s",
                config[acc.metric_names], config[acc.metric_namespace])

    if not config[acc.metric_names] or config[acc.metric_names] == ".*":
        metric_names = get_default_metric_names(
            config, config[acc.metric_namespace])
        if metric_names:
            config[acc.metric_names] = metric_names
        else:
            config[acc.metric_names] = [None]

    all_metrics = []
    filtered_at_least_one_dim = False
    q = Queue.Queue()

    def _gather_results_wrapper(metric_name, logging_ctx):
        with logging.LogContext(prefix=logging_ctx):
            _gather_results(metric_name)

    def _gather_results(metric_name):
        tacommon.set_proxy_env(config)
        try:
            server_uri = config[tac.server_uri]
            session_key = config[tac.session_key]
            aws_account = config[tac.aws_account]
            aws_iam_role = config[tac.aws_iam_role]
            credentials = tacommon.load_credentials_from_cache(
                server_uri,
                session_key,
                aws_account,
                aws_iam_role
            )
            client = boto3.client(
                "cloudwatch",
                region_name=config[tac.region],
                aws_access_key_id=credentials.aws_access_key_id,
                aws_secret_access_key=credentials.aws_secret_access_key,
                aws_session_token=credentials.aws_session_token
            )

            (metrics, filtered) = list_metrics_by_metric_name(
                client, config[acc.metric_namespace], metric_name,
                dimension_regex_filters)

            if scutil.is_true(os.environ.get("cloudwatch_filter", "true")):
                metrics = filter_invalid_dimensions(
                    config[acc.metric_namespace], metrics, config)
            q.put((metrics, filtered))
        except Exception:
            logger.exception("Failed to list metric.",
                             datainput=config[tac.datainput],
                             metric_name=metric_name,
                             namespace=config[acc.metric_namespace],
                             region=config[tac.region])

    thrs = []
    for metric_name in config[acc.metric_names]:
        thr = threading.Thread(target=_gather_results_wrapper,
                               args=(metric_name, logging.ThreadLocalLoggingStack.top()))
        thr.start()
        thrs.append(thr)

    for thr in thrs:
        thr.join()

    logger.info("Finished querying metrics for metric_names=%s, namespace=%s",
                config[acc.metric_names], config[acc.metric_namespace])
    while 1:
        try:
            (result, filtered) = q.get(block=False)
            all_metrics.extend(result)
            filtered_at_least_one_dim |= filtered
        except Queue.Empty:
            break
    if not all_metrics and filtered_at_least_one_dim:
        logger.error("No valid metrics were returned under this metric dimension",
                     ErrorCode="ConfigurationError")

    return all_metrics


class DimensionExactMatcher():

    def __init__(self, re_value_dict):
        self.regexes = {}
        for key in re_value_dict:
            if not isinstance(re_value_dict[key], list):
                re_value_dict[key] = [re_value_dict[key]]

            self.regexes[key] = []
            for regex_str in re_value_dict[key]:
                if not regex_str.endswith('$'):
                    regex_str = regex_str + '$'
                self.regexes[key].append(re.compile(regex_str))

    def exact_match(self, dimension):
        dimension = {dim["Name"]: dim["Value"] for dim in dimension}

        if len(self.regexes) != len(dimension):
            return False

        for key in self.regexes:
            if key not in dimension:
                return False

            for regex in self.regexes[key]:
                if isinstance(dimension[key], list):
                    matched = False
                    for value in dimension[key]:
                        if regex.match(value):
                            matched = True
                            break
                    if not matched:
                        return False
                else:
                    if not regex.match(dimension[key]):
                        return False
        return True


def get_dimension_filters(dimension_re_list):
    if not dimension_re_list:
        return []

    if not isinstance(dimension_re_list, list):
        dimension_re_list = [dimension_re_list]

    return [DimensionExactMatcher(re_value_dict)
            for re_value_dict in dimension_re_list]


def get_metrics(config):
    with logging.LogContext(metrics_dimensions=config[acc.metric_dimensions]):
        dimension_filters = get_dimension_filters(config[acc.metric_dimensions])
        metrics = list_metrics(config, dimension_filters)
    return metrics


def get_default_metric_names(config, namespace):
    # Get default metric names for standard namespace
    url = ("{server_uri}/servicesNS/-/-/splunk_ta_aws/"
           "splunk_ta_aws_cloudwatch_default_settings?namespace={namespace}&"
           "output_mode=json").format(
               server_uri=config["server_uri"], namespace=namespace)
    response, content = sr.splunkd_request(url, config[tac.session_key])
    if not response or response.status not in (200, 201):
        return None

    content = json.loads(content)
    metrics = json.loads(content["entry"][0]["content"]["metrics"])
    logger.info(
        "Got default metric_names=%s for namespace=%s", metrics, namespace)
    return metrics


class MetricDimensionMonitor(object):

    def __init__(self, stanzas, callback):
        self._stanzas = stanzas
        self._callback = callback

    def check_changes(self):
        # We only do lazy check for the number since do full comprehensive
        # check may introduce substential cost of memory if there are millions
        # of dimension

        logger.info("Check if there are new dimensions/metrics")
        for stanza in self._stanzas:
            for region in stanza[tac.aws_region].split(","):
                region = region.strip()
                if not region:
                    continue

                metrics = get_metrics(stanza)
                if len(metrics) != stanza[region]:
                    logger.info("Detect dimension/metrics changes")
                    if self._callback is not None:
                        self._callback()