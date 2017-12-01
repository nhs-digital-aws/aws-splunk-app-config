import os.path as op
import copy

# FIXME Legacy code started
import splunk_ta_aws.common.proxy_conf as tpc
# Legacy code done

import splunk_ta_aws.common.ta_aws_consts as tac
import aws_config_rule_consts as acc

import splunktalib.file_monitor as fm
import splunktalib.conf_manager.conf_manager as cm
from splunktalib.common import util as scutil

from splunksdc import logging
import splunk_ta_aws.common.ta_aws_common as tacommon
from splunk_ta_aws import set_log_level

logger = logging.get_module_logger()


def create_conf_monitor(callback):
    files = (AWSConfigRuleConf.app_file,
             AWSConfigRuleConf.task_file_w_path,
             AWSConfigRuleConf.passwords_file_w_path,
             AWSConfigRuleConf.conf_file_w_path)

    return fm.FileMonitor(callback, files)


class AWSConfigRuleConf(object):

    app_dir = scutil.get_app_path(op.abspath(__file__))
    app_file = op.join(app_dir, "local", "app.conf")
    passwords = "passwords"
    passwords_file_w_path = op.join(app_dir, "local", passwords + ".conf")
    task_file = "aws_config_rule_tasks"
    task_file_w_path = op.join(app_dir, "local", task_file + ".conf")
    conf_file = "aws_config_rule"
    conf_file_w_path = op.join(app_dir, "local", conf_file + ".conf")

    def __init__(self):
        self.metas, self.stanza_configs = tacommon.get_modinput_configs()
        self.metas[tac.app_name] = tac.splunk_ta_aws

    def get_tasks(self):
        conf_mgr = cm.ConfManager(self.metas[tac.server_uri],
                                  self.metas[tac.session_key])
        tasks = self._get_config_rule_tasks(conf_mgr)

        settings = conf_mgr.all_stanzas_as_dicts(
            self.conf_file, do_reload=False)
        proxy_info = tpc.get_proxy_info(self.metas[tac.session_key])
        # set proxy here for validating credentials
        tacommon.set_proxy_env(proxy_info)

        set_log_level(settings[tac.log_stanza][tac.log_level])

        valid_tasks = []
        for task in tasks:
            try:
                # validate credentials
                tacommon.get_service_client(task, tac.config)
                task[tac.log_level] = settings[tac.log_stanza][tac.log_level]
                task.update(settings[tac.global_settings])
                task.update(proxy_info)
                valid_tasks.append(task)
            except Exception as e:
                input_name = scutil.extract_datainput_name(task[tac.name])
                logger.exception('Failed to load credentials, ignore this input.',
                                 datainput=input_name)
        return tacommon.handle_hec(valid_tasks, "aws_config_rule")

    def _get_config_rule_tasks(self, conf_mgr):
        stanzas = conf_mgr.all_stanzas(self.task_file, do_reload=False)

        tasks = []
        for stanza in stanzas:
            if scutil.is_true(stanza.get(tac.disabled)):
                continue

            stanza[tac.server_uri] = self.metas[tac.server_uri]
            stanza[tac.session_key] = self.metas[tac.session_key]
            # Normalize tac.account to tac.aws_account
            stanza[tac.aws_account] = stanza.get(tac.account)
            tasks.extend(self._expand_tasks(stanza))
        return tasks

    def _expand_tasks(self, stanza):
        tasks = []
        regions = stanza[tac.region].split(",")
        rule_names = stanza.get(acc.rule_names, [])
        if rule_names:
            names = rule_names
            rule_names = []
            for rule in names.split(","):
                rule = rule.strip()
                if rule:
                    rule_names.append(rule)

        for region in regions:
            task = copy.copy(stanza)
            task[tac.region] = region.strip()
            task[tac.polling_interval] = int(stanza[tac.polling_interval])
            task[tac.is_secure] = True
            task[tac.datainput] = task[tac.stanza_name]
            task[acc.rule_names] = rule_names
            task.update(self.metas)
            tasks.append(task)

        return tasks
