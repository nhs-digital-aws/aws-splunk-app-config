#!/usr/bin/python

"""
This is the main entry point for AWS Inspector Modinput
"""

import time

import aws_inspector_consts as aiconst
from splunksdc import log as logging
import splunktalib.common.util as scutil
import splunktalib.data_loader_mgr as dlm
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import aws_inspector_conf as aiconf
import aws_inspector_data_loader as aidl


logger = logging.get_module_logger()


def print_scheme():
    title = "AWS Inspector"
    description = "Collect and index AWS Inspector findings"
    tacommon.print_scheme(title, description)


def _do_run():
    meta_configs, _, tasks = tacommon.get_configs(
        aiconf.AWSInspectorConf, "aws_inspector", logger)

    if not tasks:
        return

    meta_configs[tac.log_file] = aiconst.inspector_log
    loader_mgr = dlm.create_data_loader_mgr(meta_configs)
    tacommon.setup_signal_handler(loader_mgr, logger)
    conf_change_handler = tacommon.get_file_change_handler(loader_mgr, logger)
    conf_monitor = aiconf.create_conf_monitor(conf_change_handler)
    loader_mgr.add_timer(conf_monitor, time.time(), 10)

    jobs = [aidl.AWSInspectorDataLoader(task) for task in tasks]
    loader_mgr.run(jobs)


@scutil.catch_all(logger, False)
def run():
    """
    Main loop. Run this TA forever
    """

    logger.info("Start aws_inspector")
    _do_run()
    logger.info("End aws_inspector")


def main():
    """
    Main entry point
    """
    logging.setup_root_logger(app_name='splunk_ta_aws', modular_name='inspector')
    tacommon.main(print_scheme, run)


if __name__ == "__main__":
    main()
