import os.path as op
import copy
import traceback

import splunktalib.file_monitor as fm
import splunktalib.conf_manager.conf_manager as cm
from splunktalib.common import util as scutil
import splunksdc.log as logging

from splunk_ta_aws import set_log_level
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.proxy_conf as tpc
import splunk_ta_aws.common.ta_aws_consts as tac
import aws_kinesis_common as akcommon
import aws_kinesis_checkpointer as ackpt
import aws_kinesis_consts as akc


logger = logging.get_module_logger()


def create_conf_monitor(callback):
    files = (AWSKinesisConf.app_file,
             AWSKinesisConf.task_file_w_path,
             AWSKinesisConf.passwords_file_w_path,
             AWSKinesisConf.conf_file_w_path)

    return fm.FileMonitor(callback, files)


class AWSKinesisConf(object):

    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")
    task_file = "aws_kinesis_tasks"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    conf_file = "aws_kinesis"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        conf_mgr = cm.ConfManager(self.metas[tac.server_uri],
                                  self.metas[tac.session_key])
        all_tasks = self._get_kinesis_tasks(conf_mgr)

        settings = conf_mgr.all_stanzas_as_dicts(
            self.conf_file, do_reload=False)

        # set logging level for our logger
        set_log_level(settings[tac.log_stanza][tac.log_level])

        for task in all_tasks:
            task[tac.log_level] = settings[tac.log_stanza][tac.log_level]
            task.update(settings[tac.global_settings])

        ackpt.clean_up_ckpt_for_deleted_data_input(all_tasks)

        return tacommon.handle_hec(all_tasks, "aws_kinesis")

    def _get_kinesis_tasks(self, conf_mgr):
        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])
        stanzas = conf_mgr.all_stanzas(self.task_file, do_reload=False)

        tasks, creds = [], {}
        for stanza in stanzas:
            if scutil.is_true(stanza[tac.disabled]):
                continue
            # Normalize tac.account to tac.aws_account
            stanza[tac.aws_account] = stanza.get(tac.account)
            stanza[tac.aws_iam_role] = stanza.get(tac.aws_iam_role)
            tasks.extend(self._expand_tasks(stanza, creds, proxy_info))

        return tasks

    def _expand_tasks(self, stanza, creds, proxy_info):
        names = stanza[akc.stream_names].split(",")
        stream_names = []
        for name in names:
            name = name.strip()
            if name:
                stream_names.append(name)

        stanza.update(proxy_info)
        stanza.update(self.metas)

        try:
            client = akcommon.KinesisClient(stanza, logger)
            streams = client.describe_streams(stream_names)
        except Exception as e:
            if "ResourceNotFoundException" in e.message:
                logger.info(
                    "stream=%s in region=%s has been deleted, please "
                    "delete datainput=%s", stream_names,
                    stanza[tac.region], stanza[tac.stanza_name])
                return []
            else:
                logger.error(
                    "Failed to describe stream=%s in region=%s, for "
                    "datainput=%s, ignore this datainput. error=%s",
                    stream_names, stanza[tac.region], stanza[tac.stanza_name],
                    traceback.format_exc())
                return []

        tasks = []
        for stream_name in stream_names:
            for shard in streams[stream_name]["Shards"]:
                task = copy.copy(stanza)
                task[tac.datainput] = task[tac.stanza_name]
                task[tac.aws_service] = tac.kinesis
                task[akc.stream_name] = stream_name
                task[akc.shard_id] = shard["ShardId"]
                tasks.append(task)

        return tasks


class ShardChangesChecker(object):

    """
    Monitor Kinesis shard split/merge
    """

    def __init__(self, config, streams, callback):
        """
        :config: dict contains secret_key/id/region/proxy/session_key etc
        :streams: a list of string which contains stream_names
        """

        self._config = config
        self._streams = streams
        self._callback = callback
        self._stream_shards = self._get_stream_shards()

    def __call__(self):
        self.check_changes()

    def check_changes(self):
        logger.debug("Check shard changes")
        stream_shards = self._get_stream_shards()
        if len(stream_shards) != len(self._stream_shards):
            logger.info("Detect stream deletion")
            if self._callback is not None:
                return self._callback()

        for stream_name, shards in stream_shards.iteritems():
            if len(self._stream_shards[stream_name]) != len(shards):
                logger.info(
                    "Detect shard changes for stream_name=%s", stream_name)
                if self._callback is not None:
                    return self._callback()

    def _get_stream_shards(self):
        client = akcommon.KinesisClient(self._config, logger)
        try:
            streams = client.describe_streams(self._streams)
        except Exception as e:
            if "ResourceNotFoundException" in e.message:
                return {}
            else:
                logger.error(
                    "Failed to describe streams, error=%s",
                    traceback.format_exc())
                raise

        stream_shards = {}
        for stream_name, stream in streams.iteritems():
            shards = [shard["ShardId"] for shard in stream["Shards"]]
            stream_shards[stream_name] = shards
        return stream_shards
