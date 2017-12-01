#!/usr/bin/python

"""
This is the main entry point for AWS Config Rules Modinput
"""

import time

from splunksdc import logging
import splunktalib.common.util as scutil
import splunktalib.data_loader_mgr as dlm
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import aws_config_rule_consts as acc
import aws_config_rule_conf as arc
import aws_config_rule_data_loader as ardl

logger = logging.get_module_logger()


def print_scheme():
    title = "AWS Config Rules"
    description = "Collect and index Config Rules for AWS services"
    tacommon.print_scheme(title, description)


def _do_run():
    meta_configs, _, tasks = tacommon.get_configs(
        arc.AWSConfigRuleConf, "aws_config_rule", logger)

    if not tasks:
        return

    meta_configs[tac.log_file] = acc.config_log
    loader_mgr = dlm.create_data_loader_mgr(meta_configs)
    tacommon.setup_signal_handler(loader_mgr, logger)
    conf_change_handler = tacommon.get_file_change_handler(loader_mgr, logger)
    conf_monitor = arc.create_conf_monitor(conf_change_handler)
    loader_mgr.add_timer(conf_monitor, time.time(), 10)

    jobs = [ardl.ConfigRuleDataLoader(task) for task in tasks]
    loader_mgr.run(jobs)


@scutil.catch_all(logger, False)
def run():
    """
    Main loop. Run this TA forever
    """

    logger.info("Start aws_config_rule")
    _do_run()
    logger.info("End aws_config_rule")


def main():
    """
    Main entry point
    """
    logging.setup_root_logger(app_name="splunk_ta_aws", modular_name='config_rule')
    tacommon.main(print_scheme, run)


if __name__ == "__main__":
    main()
