import os.path as op
import datetime
from splunktalib.common.util import extract_datainput_name
import splunktalib.file_monitor as fm
import splunktalib.conf_manager.conf_manager as cm
import splunktalib.common.util as scutil
import splunksdc.log as logging
from splunk_ta_aws import set_log_level
import splunk_ta_aws.common.proxy_conf as tpc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import aws_s3_common as s3common
import aws_s3_checkpointer as s3ckpt
import aws_s3_consts as asc


# logger needs to be get consistently throughout the mod-input
logger = logging.get_module_logger()


def create_conf_monitor(callback):
    files = (AWSS3Conf.app_file,
             AWSS3Conf.passwords_file_w_path,
             AWSS3Conf.log_info_w_path)

    return fm.FileMonitor(callback, files)


class AWSS3Conf(object):

    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    task_file = "inputs"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")
    log_info = "log_info"
    log_info_w_path = op.join(app_dir, "local", log_info + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        with logging.LogContext(phase="prepare"):
            return self._get_tasks()

    def _get_tasks(self):
        if not self.stanza_configs:
            return None

        conf_mgr = cm.ConfManager(self.metas[tac.server_uri],
                                  self.metas[tac.session_key])
        logging_settings = conf_mgr.get_stanza(
            self.log_info, asc.log_stanza, do_reload=False)
        # set the log level read from conf for our logger
        set_log_level(logging_settings[asc.log_level])

        # entry point for this stanza task, setup root logger here
        # Generic S3 can be configured to be single-instance
        # or multiple instance
        # through env variable
        stanza_name = ''
        try:
            if len(self.stanza_configs) == 1:
                # only one stanza exists
                stanza_name = self.stanza_configs[0].get('name', '')
        except Exception:
            logger.exception('Failed to get stanza name!')

        stanza_name = extract_datainput_name(stanza_name)
        logging.setup_root_logger(app_name=tac.splunk_ta_aws,
                                  modular_name=asc.mod_name,
                                  stanza_name=stanza_name)

        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])
        tasks, creds = [], {}
        for stanza in self.stanza_configs:
            task = {}
            task.update(stanza)
            task.update(self.metas)
            task.update(proxy_info)
            task[tac.log_level] = logging_settings[asc.log_level]
            task[tac.interval] = tacommon.get_interval(task, 3600)
            task[tac.polling_interval] = task[tac.interval]
            task[asc.max_retries] = int(task.get(asc.max_retries, 3))
            task[asc.prefix] = task.get(asc.key_name)
            task[asc.last_modified] = self._get_last_modified_time(
                task[asc.initial_scan_datetime])
            task[asc.terminal_scan_datetime] = self._convert_terminal_scan_datetime(
                task.get(asc.terminal_scan_datetime))
            input_name = scutil.extract_datainput_name(task[tac.name])
            task[asc.data_input] = input_name
            task[tac.sourcetype] = task.get(tac.sourcetype, "aws:s3")
            task[asc.bucket_name] = str(task[asc.bucket_name])
            if not task.get(asc.whitelist):
                task[asc.whitelist] = s3common.sourcetype_to_keyname_regex.get(
                    task[tac.sourcetype])
            tasks.append(task)
            logger.info("Done with configuration read from conf.")
        s3ckpt.handle_ckpts(tasks)
        return tasks

    def _get_last_modified_time(self, scan_datetime):
        if not scan_datetime or scan_datetime.strip() == "default":
            stime = datetime.datetime.utcnow() + datetime.timedelta(days=-7)
        else:
            stime = tacommon.parse_datetime(
                self.metas[tac.server_uri], self.metas[tac.session_key],
                scan_datetime)
        return stime.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _convert_terminal_scan_datetime(self, terminal_scan_datetime):
        if not terminal_scan_datetime:
            return 'z'
        else:
            stime = tacommon.parse_datetime(
                self.metas[tac.server_uri],
                self.metas[tac.session_key],
                terminal_scan_datetime,
            )
            return stime.strftime("%Y-%m-%dT%H:%M:%S.000Z")
