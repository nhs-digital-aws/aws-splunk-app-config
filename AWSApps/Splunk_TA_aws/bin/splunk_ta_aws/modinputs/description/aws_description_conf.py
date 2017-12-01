import os.path as op
import splunk_ta_aws.common.proxy_conf as tpc
from splunk_ta_aws import set_log_level
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import aws_description_consts as adc

import splunktalib.file_monitor as fm
import splunktalib.conf_manager.conf_manager as cm

import splunksdc.log as logging
from splunktalib.common import util as scutil


logger = logging.get_module_logger()


def create_conf_monitor(callback):
    files = (AWSDescribeConf.app_file,
             AWSDescribeConf.conf_file_w_path,
             AWSDescribeConf.task_file_w_path,
             AWSDescribeConf.passwords_file_w_path)

    return fm.FileMonitor(callback, files)


class AWSDescribeConf(object):
    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    conf_file = "aws_description"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")
    task_file = "aws_description_tasks"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        conf_mgr = cm.ConfManager(self.metas[tac.server_uri],
                                  self.metas[tac.session_key])
        tasks = self._get_description_tasks(conf_mgr)

        logging_settings = conf_mgr.get_stanza(
            self.conf_file, tac.log_stanza, do_reload=False)

        # set logging level for our logger
        set_log_level(logging_settings[tac.log_level])

        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])

        # Set proxy for loading credentials by boto3
        tacommon.set_proxy_env(proxy_info)

        for task in tasks:
            task[tac.log_level] = logging_settings[tac.log_level]
            task.update(proxy_info)

        self._assign_source(tasks)
        return tasks

    def _get_description_tasks(self, conf_mgr):
        stanzas = conf_mgr.all_stanzas(self.task_file, do_reload=False)

        tasks, creds = [], {}
        for stanza in stanzas:
            if scutil.is_true(stanza.get(tac.disabled)):
                continue

            # Normalize tac.account to tac.aws_account
            stanza[tac.aws_account] = stanza.get(tac.account)
            tasks.extend(self._expand_tasks(stanza, creds))
        return tasks

    def _expand_tasks(self, stanza, creds):
        tasks = []
        for api_interval in stanza[adc.apis].split(","):
            api_interval = api_interval.split("/")
            api_name = api_interval[0].strip()
            api_interval = int(api_interval[1].strip())

            for region in stanza[tac.regions].split(","):
                region = region.strip()

                tasks.append({
                    tac.server_uri: self.metas[tac.server_uri],
                    tac.session_key: self.metas[tac.session_key],
                    tac.aws_account: stanza[tac.aws_account],
                    tac.aws_iam_role: stanza.get(tac.aws_iam_role),
                    tac.region: region,
                    adc.api: api_name,
                    tac.interval: api_interval,
                    tac.is_secure: True,
                    tac.index: stanza[tac.index],
                    tac.sourcetype: stanza[tac.sourcetype],
                    tac.datainput: stanza[tac.name]
                })

                if api_name in adc.global_resources:
                    break

        return tasks

    def _assign_source(self, tasks):
        for task in tasks:
            if not task.get(tac.source):
                task[tac.source] = "{region}:{api}".format(**task)
